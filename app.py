from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, url_for, session, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf, validate_csrf
from config import Config
import uuid
from datetime import datetime
import os
import re
import html
import hashlib
from werkzeug.utils import secure_filename
from sqlalchemy import text

# Temporarily disable advanced error handling to fix deployment
# from error_handlers import (
#     handle_api_errors, validate_json_request, require_uuid, log_api_request,
#     register_error_handlers, APIException, ValidationException, NotFoundException,
#     UnauthorizedException, ForbiddenException, ConflictException
# )
# from validation_schemas import (
#     chat_message_schema, project_schema, conversation_schema, context_item_schema,
#     user_preferences_schema, validate_request_data, create_validation_error_response,
#     validate_uuid, validate_file_upload
# )

from PyPDF2 import PdfReader
import io
try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

# Initialize Flask app
app = Flask(__name__, static_folder='static', instance_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance'))

# Force template reloading in production (Railway cache issue)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# Configure app based on environment
from config import config
config_name = os.getenv('FLASK_CONFIG', 'default')
app.config.from_object(config[config_name])
config[config_name].init_app(app)

def build_project_system_prompt(project):
    """Build a structured system prompt from project template data"""
    if not project:
        return None
    
    # Check if project has any template data
    has_template_data = any([
        project.agent_name, 
        project.agent_role, 
        project.primary_goal,
        project.goal_steps,
        project.rules_do,
        project.rules_dont,
        project.context_background,
        project.output_format
    ])
    
    if not has_template_data:
        return None
    
    prompt_parts = []
    
    # Identity & Persona Section
    if project.agent_name or project.agent_role or project.agent_personality:
        prompt_parts.append("# IDENTITY & PERSONA")
        
        if project.agent_name and project.agent_role:
            personality = f", {project.agent_personality}" if project.agent_personality else ""
            prompt_parts.append(f"You are {project.agent_name}, a {project.agent_role}. Your personality is {project.agent_personality.strip(', ')}.{personality}")
        elif project.agent_name:
            prompt_parts.append(f"You are {project.agent_name}.")
        elif project.agent_role:
            prompt_parts.append(f"You are a {project.agent_role}.")
        
        if project.agent_personality and not (project.agent_name and project.agent_role):
            prompt_parts.append(f"Your personality is {project.agent_personality}.")
    
    # Task & Goal Section
    if project.primary_goal or project.goal_steps:
        prompt_parts.append("\n# TASK & GOAL")
        
        if project.primary_goal:
            prompt_parts.append(f"Your primary goal is to {project.primary_goal}")
        
        if project.goal_steps:
            try:
                import json
                steps = json.loads(project.goal_steps)
                if steps and isinstance(steps, list):
                    prompt_parts.append("You will accomplish this by following these steps:")
                    for i, step in enumerate(steps, 1):
                        prompt_parts.append(f"{i}. {step}")
            except (json.JSONDecodeError, TypeError):
                # Handle case where goal_steps is a plain string
                if project.goal_steps.strip():
                    prompt_parts.append("Steps to follow:")
                    for line in project.goal_steps.split('\n'):
                        if line.strip():
                            prompt_parts.append(f"• {line.strip()}")
    
    # Rules & Constraints Section
    if project.rules_do or project.rules_dont:
        prompt_parts.append("\n# RULES & CONSTRAINTS")
        
        if project.rules_do:
            try:
                import json
                do_rules = json.loads(project.rules_do)
                if do_rules and isinstance(do_rules, list):
                    for rule in do_rules:
                        prompt_parts.append(f"- DO: {rule}")
            except (json.JSONDecodeError, TypeError):
                # Handle case where rules_do is a plain string
                if project.rules_do.strip():
                    for line in project.rules_do.split('\n'):
                        if line.strip():
                            prompt_parts.append(f"- DO: {line.strip()}")
        
        if project.rules_dont:
            try:
                import json
                dont_rules = json.loads(project.rules_dont)
                if dont_rules and isinstance(dont_rules, list):
                    for rule in dont_rules:
                        prompt_parts.append(f"- DO NOT: {rule}")
            except (json.JSONDecodeError, TypeError):
                # Handle case where rules_dont is a plain string
                if project.rules_dont.strip():
                    for line in project.rules_dont.split('\n'):
                        if line.strip():
                            prompt_parts.append(f"- DO NOT: {line.strip()}")
    
    # Context Section
    if project.context_background or project.user_role:
        prompt_parts.append("\n# CONTEXT")
        
        if project.context_background:
            prompt_parts.append(f"The context for our conversation is {project.context_background}")
        
        if project.user_role:
            prompt_parts.append(f"I, the user, am a {project.user_role}.")
    
    # Output Format Section
    if project.output_format:
        prompt_parts.append("\n# OUTPUT FORMAT")
        prompt_parts.append(project.output_format)
    
    return '\n'.join(prompt_parts) if prompt_parts else None

# Security configurations
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Setup logging
from logger import setup_logging
setup_logging(app)

# Initialize database
from database import db, init_db
db = init_db(app)

CORS(app)

# CSRF Protection
csrf = CSRFProtect(app)

# Register error handlers (temporarily disabled)
# register_error_handlers(app)

# Custom CSRF validation for API endpoints
def validate_csrf_for_api():
    """Custom CSRF validation for API endpoints that expect JSON"""
    if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
        # Check for CSRF token in headers or JSON body
        csrf_token = request.headers.get('X-CSRFToken')
        if not csrf_token and request.is_json:
            data = request.get_json(silent=True)
            if data:
                csrf_token = data.get('csrf_token')
        
        if csrf_token:
            try:
                validate_csrf(csrf_token)
            except Exception as e:
                return jsonify({'error': 'CSRF token validation failed'}), 403
        else:
            return jsonify({'error': 'CSRF token required'}), 403
    return None

# Ensure CSRF token is available to all templates as a simple string
@app.context_processor
def inject_csrf_token():
    try:
        token = generate_csrf()
    except Exception:
        token = ''
    return {'csrf_token': token}

# CSRF protection is enabled globally
# Individual routes can be exempted using @csrf.exempt decorator

# Rate limiting - use in-memory for simplicity
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"]
)
limiter.init_app(app)

# Import models after db initialization
from models import Conversation, Message, Attachment, Project, ContextItem, Persona
from user_models import User, UserRole, UserStatus, Organization, UserSession, UserAuditLog
from context_service import ContextService
from llm_service import LLMService

# Initialize authentication
from auth import auth
from security_utils import (
    require_conversation_access, require_message_access, require_project_access,
    require_context_item_access, get_user_identity, check_conversation_access,
    sanitize_filename
)
auth.init_app(app)

llm_service = LLMService()

# Security configuration validation
def validate_security_config():
    """Validate critical security configurations on startup"""
    issues = []
    
    # Check SECRET_KEY
    secret_key = app.config.get('SECRET_KEY', '')
    if not secret_key or len(secret_key) < 32:
        issues.append("SECRET_KEY is too short or missing - minimum 32 characters required")
    if 'dev-key' in secret_key.lower() or 'insecure' in secret_key.lower():
        issues.append("SECRET_KEY appears to be a development key - change immediately in production")
    
    # Check AUTH_PASSWORD if set
    auth_password = os.getenv('AUTH_PASSWORD', '')
    if auth_password and not auth_password.startswith(('$2b$', '$2a$', '$2y$', 'pbkdf2:', 'scrypt:')):
        issues.append("AUTH_PASSWORD should be hashed - use werkzeug.security.generate_password_hash()")
    
    # Check FLASK_CONFIG
    flask_config = os.getenv('FLASK_CONFIG', 'development')
    if flask_config == 'development' and not app.debug:
        issues.append("FLASK_CONFIG set to development but DEBUG is False - verify configuration")
    
    if issues:
        for issue in issues:
            app.logger.warning(f"SECURITY WARNING: {issue}")
        
        # In production, these should be fatal errors
        if not app.debug:
            app.logger.error("Critical security issues detected in production mode")

# Run security validation on startup
validate_security_config()

@app.route('/test-endpoint')
def test_endpoint():
    """Simple test endpoint to verify deployment"""
    return jsonify({
        'status': 'working',
        'message': 'Endpoint is accessible',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/migrate-add-indexes')
def migrate_add_indexes():
    """
    Web endpoint to add database indexes for performance
    Only run this once after deployment
    """
    try:
        from sqlalchemy import text
        
        # Log the migration attempt
        app.logger.info("Starting database index migration via web endpoint")
        
        # Define indexes to create (simplified for reliability)
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_created ON conversations(user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_project_created ON conversations(project_id, created_at)", 
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation_timestamp ON messages(conversation_id, timestamp)",
        ]
        
        created_indexes = []
        failed_indexes = []
        
        # Create indexes one by one
        for i, index_sql in enumerate(indexes):
            try:
                db.session.execute(text(index_sql))
                db.session.commit()
                index_name = f"index_{i+1}"
                created_indexes.append(index_name)
                app.logger.info(f"Created index: {index_name}")
            except Exception as e:
                failed_indexes.append(f"index_{i+1}: {str(e)}")
                app.logger.error(f"Failed to create index {i+1}: {e}")
        
        app.logger.info("Database index migration completed")
        
        return jsonify({
            'success': True,
            'message': f'Database indexes migration completed',
            'created': len(created_indexes),
            'failed': len(failed_indexes),
            'details': {
                'created_indexes': created_indexes,
                'failed_indexes': failed_indexes
            }
        })
        
    except Exception as e:
        app.logger.error(f"Database index migration failed: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Database index migration failed',
            'error': str(e)
        }), 500

# Import get_user_identity from security_utils to avoid duplication
from security_utils import get_user_identity

def filter_conversations_by_user(query):
    """Filter conversations by current user identity"""
    identity = get_user_identity()
    
    if identity['type'] == 'authenticated':
        # Authenticated admin: show ALL conversations (user_id is None for admin)
        if identity['user_id'] is None:
            return query  # No filter - admin sees everything
        # Regular authenticated user: only show their conversations
        # user_id is stored as string (VARCHAR in database)
        return query.filter(Conversation.user_id == identity['user_id'])
    else:
        # Free user: only show conversations that:
        # 1. Have the same session_id (primary match)
        # 2. OR have same IP but NO user_id (legacy free conversations)
        return query.filter(Conversation.session_id == identity['session_id'])

# File upload configuration
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'docx', 'doc', 'csv', 
    'jpg', 'jpeg', 'png', 'gif', 'webp',  # For image editing
    'mp3', 'wav', 'ogg', 'flac'  # For audio transcription
}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_size(file):
    """Validate file size"""
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to beginning
    return size <= MAX_FILE_SIZE

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'message': 'AI Knowledge Base API is running'})

@app.route('/')
def index():
    has_access, access_type, free_info = auth.has_access()
    if not has_access:
        return redirect(url_for('login_page'))
    return render_template('app_main.html')

# Test routes removed - main route now uses new template structure

@app.route('/login')
def login_page():
    if auth.is_authenticated():
        return redirect(url_for('index'))
    return render_template('login.html')

@csrf.exempt
@app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    """Get CSRF token for AJAX requests"""
    try:
        token = generate_csrf()
        return jsonify({'csrf_token': token}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to generate CSRF token'}), 500

# Configure CSRF exemptions for auth endpoints
@csrf.exempt
@app.route('/auth/logout', methods=['POST'])
def logout_override():
    """Logout endpoint - bypassing auth.py registration to add CSRF exemption"""
    from flask import session
    
    # Log logout for regular users
    user_id = session.get('user_id')
    if user_id and user_id != 'admin':
        try:
            audit_log = UserAuditLog(
                user_id=user_id,
                action='logout',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                success=True
            )
            db.session.add(audit_log)
            db.session.commit()
        except Exception as e:
            app.logger.error(f"Error logging logout: {e}")
    
    # Clear all session data
    session.pop('authenticated', None)
    session.pop('user_id', None)
    session.pop('user_type', None)
    session.pop('user_role', None)
    session.pop('username', None)
    session.pop('display_name', None)
    
    return jsonify({'success': True, 'message': 'Logged out'})

@csrf.exempt  
@app.route('/auth/login', methods=['POST'])
def login_override():
    """Login endpoint - supports both admin (password only) and users (username + password)"""
    from flask import session
    from datetime import datetime
    
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    # Check if this is an admin login (password only, no username)
    if not username and password:
        if auth.verify_password(password):
            session['authenticated'] = True
            session['user_id'] = None  # Set to None for now - will fix after database is properly migrated
            session['user_type'] = 'admin'
            session['user_role'] = 'SUPER_ADMIN'
            app.logger.info("Admin login successful")
            return jsonify({
                'success': True, 
                'message': 'Admin login successful',
                'user_type': 'admin',
                'user_role': 'SUPER_ADMIN'
            })
        else:
            return jsonify({'success': False, 'error': 'Invalid admin password'}), 401
    
    # Check if this is a regular user login (username + password)
    elif username and password:
        user = db.session.query(User).filter(
            User.username == username,
            User.status == UserStatus.ACTIVE
        ).first()
        
        if user and user.check_password(password):
            # Update user login stats
            user.last_login_at = datetime.utcnow()
            user.login_count += 1
            user.last_activity_at = datetime.utcnow()
            db.session.commit()
            
            # Set session
            session['authenticated'] = True
            session['user_id'] = str(user.id)
            session['user_type'] = 'user'
            session['user_role'] = user.role.value
            session['username'] = user.username
            session['display_name'] = user.display_name or user.username
            session['email'] = user.email
            session['first_name'] = user.first_name
            session['last_name'] = user.last_name
            
            # Log the login
            audit_log = UserAuditLog(
                user_id=user.id,
                action='login',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                success=True
            )
            db.session.add(audit_log)
            db.session.commit()
            
            app.logger.info(f"User login successful: {username} (role: {user.role.value})")
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user_type': 'user',
                'user_role': user.role.value,
                'username': user.username,
                'display_name': user.display_name or user.username
            })
        else:
            # Log failed attempt
            if user:
                audit_log = UserAuditLog(
                    user_id=user.id,
                    action='login',
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    success=False,
                    error_message='Invalid password'
                )
                db.session.add(audit_log)
                db.session.commit()
            
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401
    
    else:
        return jsonify({'success': False, 'error': 'Please provide either admin password or username and password'}), 400


@app.route('/init-db')
def init_database():
    try:
        db.create_all()
        return jsonify({'message': 'Database initialized successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== USER MANAGEMENT API ENDPOINTS ====================

@app.route('/api/users', methods=['GET'])
@auth.login_required
def get_users():
    """Get all users (admin only)"""
    try:
        # Check if user is admin
        user_type = session.get('user_type')
        user_role = session.get('user_role')
        
        if user_type != 'admin' and user_role not in ['super_admin', 'admin']:
            return jsonify({'error': 'Unauthorized - Admin access required'}), 403
        
        users = db.session.query(User).all()
        
        users_list = []
        for user in users:
            users_list.append({
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'display_name': user.display_name or f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                'role': user.role.value,
                'status': user.status.value,
                'last_login_at': user.last_login_at.isoformat() if user.last_login_at else None,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'login_count': user.login_count
            })
        
        return jsonify({'users': users_list, 'success': True})
        
    except Exception as e:
        app.logger.error(f"Error fetching users: {str(e)}")
        return jsonify({'error': 'Failed to fetch users'}), 500

@app.route('/api/users/<user_id>', methods=['GET'])
@auth.login_required
def get_user(user_id):
    """Get single user details (admin only)"""
    try:
        # Check if user is admin
        user_type = session.get('user_type')
        user_role = session.get('user_role')
        
        if user_type != 'admin' and user_role not in ['super_admin', 'admin']:
            return jsonify({'error': 'Unauthorized - Admin access required'}), 403
        
        user = db.session.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user_data = {
            'id': str(user.id),
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'display_name': user.display_name,
            'role': user.role.value,
            'status': user.status.value,
            'email_verified': user.email_verified,
            'last_login_at': user.last_login_at.isoformat() if user.last_login_at else None,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'login_count': user.login_count
        }
        
        return jsonify({'user': user_data, 'success': True})
        
    except Exception as e:
        app.logger.error(f"Error fetching user: {str(e)}")
        return jsonify({'error': 'Failed to fetch user'}), 500

@app.route('/api/users', methods=['POST'])
@auth.login_required
def create_user():
    """Create new user (admin only)"""
    try:
        # Check if user is admin
        user_type = session.get('user_type')
        user_role = session.get('user_role')
        
        if user_type != 'admin' and user_role not in ['super_admin', 'admin']:
            return jsonify({'error': 'Unauthorized - Admin access required'}), 403
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('username') or not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Username, email, and password are required'}), 400
        
        username = data['username'].strip()
        email = data['email'].strip()
        password = data['password']
        
        # Username validation
        if len(username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        if not username.replace('_', '').replace('-', '').replace('.', '').isalnum():
            return jsonify({'error': 'Username can only contain letters, numbers, hyphens, underscores, and periods'}), 400
        
        # Email validation
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Password strength validation
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        if not re.search(r'[A-Z]', password):
            return jsonify({'error': 'Password must contain at least one uppercase letter'}), 400
        if not re.search(r'[a-z]', password):
            return jsonify({'error': 'Password must contain at least one lowercase letter'}), 400
        if not re.search(r'\d', password):
            return jsonify({'error': 'Password must contain at least one number'}), 400
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]', password):
            return jsonify({'error': 'Password must contain at least one special character'}), 400
        
        # Check if username exists
        existing_user = db.session.query(User).filter(User.username == username).first()
        if existing_user:
            return jsonify({'error': 'Username already exists'}), 400
        
        # Check if email exists
        existing_email = db.session.query(User).filter(User.email == email).first()
        if existing_email:
            return jsonify({'error': 'Email already exists'}), 400
        
        # Create new user
        new_user = User(
            username=data['username'],
            email=data['email'],
            password=data['password']
        )
        
        # Set optional fields
        if data.get('first_name'):
            new_user.first_name = data['first_name']
        if data.get('last_name'):
            new_user.last_name = data['last_name']
        if data.get('display_name'):
            new_user.display_name = data['display_name']
        if data.get('role'):
            try:
                new_user.role = UserRole(data['role'])
            except ValueError:
                return jsonify({'error': 'Invalid role'}), 400
        if data.get('status'):
            try:
                new_user.status = UserStatus(data['status'])
            except ValueError:
                return jsonify({'error': 'Invalid status'}), 400
        
        db.session.add(new_user)
        db.session.commit()
        
        app.logger.info(f"User created: {new_user.username} by {session.get('user_id')}")
        
        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'user_id': str(new_user.id)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error creating user: {str(e)}")
        return jsonify({'error': 'Failed to create user'}), 500

@app.route('/api/users/<user_id>', methods=['PUT'])
@auth.login_required
def update_user(user_id):
    """Update user (admin only)"""
    try:
        # Check if user is admin
        user_type = session.get('user_type')
        user_role = session.get('user_role')
        
        if user_type != 'admin' and user_role not in ['super_admin', 'admin']:
            return jsonify({'error': 'Unauthorized - Admin access required'}), 403
        
        user = db.session.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Update username if changed
        if data.get('username') and data['username'] != user.username:
            existing = db.session.query(User).filter(User.username == data['username']).first()
            if existing:
                return jsonify({'error': 'Username already exists'}), 400
            user.username = data['username']
        
        # Update email if changed
        if data.get('email') and data['email'] != user.email:
            existing = db.session.query(User).filter(User.email == data['email']).first()
            if existing:
                return jsonify({'error': 'Email already exists'}), 400
            user.email = data['email']
        
        # Update password if provided
        if data.get('password'):
            password = data['password']
            import re
            if len(password) < 8:
                return jsonify({'error': 'Password must be at least 8 characters'}), 400
            if not re.search(r'[A-Z]', password):
                return jsonify({'error': 'Password must contain at least one uppercase letter'}), 400
            if not re.search(r'[a-z]', password):
                return jsonify({'error': 'Password must contain at least one lowercase letter'}), 400
            if not re.search(r'\d', password):
                return jsonify({'error': 'Password must contain at least one number'}), 400
            if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]', password):
                return jsonify({'error': 'Password must contain at least one special character'}), 400
            user.set_password(password)
        
        # Update other fields
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'display_name' in data:
            user.display_name = data['display_name']
        if data.get('role'):
            try:
                user.role = UserRole(data['role'])
            except ValueError:
                return jsonify({'error': 'Invalid role'}), 400
        if data.get('status'):
            try:
                user.status = UserStatus(data['status'])
            except ValueError:
                return jsonify({'error': 'Invalid status'}), 400
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        app.logger.info(f"User updated: {user.username} by {session.get('user_id')}")
        
        return jsonify({
            'success': True,
            'message': 'User updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating user: {str(e)}")
        return jsonify({'error': 'Failed to update user'}), 500

@app.route('/api/users/<user_id>', methods=['DELETE'])
@auth.login_required
def delete_user(user_id):
    """Delete user (admin only)"""
    try:
        # Check if user is admin
        user_type = session.get('user_type')
        user_role = session.get('user_role')
        
        if user_type != 'admin' and user_role not in ['super_admin', 'admin']:
            return jsonify({'error': 'Unauthorized - Admin access required'}), 403
        
        user = db.session.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Prevent deleting admin user
        if user.username == 'admin':
            return jsonify({'error': 'Cannot delete admin user'}), 400
        
        username = user.username
        db.session.delete(user)
        db.session.commit()
        
        app.logger.info(f"User deleted: {username} by {session.get('user_id')}")
        
        return jsonify({
            'success': True,
            'message': 'User deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting user: {str(e)}")
        return jsonify({'error': 'Failed to delete user'}), 500

@csrf.exempt
@app.route('/api/users/update-profile', methods=['PUT'])
@auth.login_required
def update_user_profile():
    """Allow users to update their own profile information"""
    try:
        data = request.get_json()
        
        # Get current user from session
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = db.session.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Extract fields from request
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        display_name = data.get('display_name', '').strip()
        current_password = data.get('current_password', '')
        new_password = data.get('new_password')
        
        # Verify current password for any changes
        if not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        # Validate required fields
        if not username:
            return jsonify({'error': 'Username is required'}), 400
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        if not display_name:
            return jsonify({'error': 'Display name is required'}), 400
        
        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Check for username conflicts (if changed)
        if username != user.username:
            existing_user = User.query.filter(User.username == username).first()
            if existing_user and existing_user.id != user.id:
                return jsonify({'error': 'Username already exists'}), 400
        
        # Check for email conflicts (if changed)
        if email.lower() != user.email.lower():
            existing_user = User.query.filter(User.email == email.lower()).first()
            if existing_user and existing_user.id != user.id:
                return jsonify({'error': 'Email already registered'}), 400
        
        # Update profile fields
        user.username = username
        user.email = email.lower()
        user.first_name = first_name
        user.last_name = last_name
        user.display_name = display_name
        
        # Update password if provided
        if new_password:
            if len(new_password) < 8:
                return jsonify({'error': 'New password must be at least 8 characters'}), 400
            if not re.search(r'[A-Z]', new_password):
                return jsonify({'error': 'Password must contain at least one uppercase letter'}), 400
            if not re.search(r'[a-z]', new_password):
                return jsonify({'error': 'Password must contain at least one lowercase letter'}), 400
            if not re.search(r'\d', new_password):
                return jsonify({'error': 'Password must contain at least one number'}), 400
            if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]', new_password):
                return jsonify({'error': 'Password must contain at least one special character'}), 400
            user.set_password(new_password)
        
        # Update last activity
        from datetime import datetime
        user.last_activity_at = datetime.utcnow()
        
        db.session.commit()
        
        # Update session
        session['username'] = username
        session['display_name'] = display_name
        
        app.logger.info(f"User profile updated: {user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'user': {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'display_name': user.display_name
            }
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating user profile: {str(e)}")
        return jsonify({'error': 'Failed to update profile'}), 500

@app.route('/migrate-project-template')
def migrate_project_template():
    """Add new template fields to the projects table if they don't exist"""
    try:
        # List of new columns to add
        new_columns = [
            ("agent_name", "VARCHAR(255)"),
            ("agent_role", "VARCHAR(500)"),
            ("agent_personality", "VARCHAR(500)"),
            ("primary_goal", "TEXT"),
            ("goal_steps", "TEXT"),
            ("rules_do", "TEXT"),
            ("rules_dont", "TEXT"),
            ("context_background", "TEXT"),
            ("user_role", "VARCHAR(500)"),
            ("output_format", "TEXT")
        ]
        
        results = []
        
        # Check which columns already exist
        try:
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'projects'
            """))
            existing_columns = [row[0] for row in result]
            results.append(f"Existing columns: {existing_columns}")
        except Exception as e:
            results.append(f"Could not check existing columns: {e}")
            existing_columns = []
        
        # Add each column if it doesn't exist
        for column_name, column_type in new_columns:
            if column_name not in existing_columns:
                try:
                    alter_sql = f"ALTER TABLE projects ADD COLUMN {column_name} {column_type}"
                    db.session.execute(text(alter_sql))
                    db.session.commit()
                    results.append(f"✓ Added column: {column_name}")
                except Exception as e:
                    results.append(f"✗ Failed to add column {column_name}: {e}")
                    db.session.rollback()
            else:
                results.append(f"○ Column {column_name} already exists")
        
        return jsonify({
            'message': 'Migration completed successfully!',
            'details': results
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Migration failed: {str(e)}'}), 500

@app.route('/projects', methods=['GET'])
@auth.login_required
def get_projects():
    from models import Project, Conversation
    
    # Get user identity to determine filtering
    identity = get_user_identity()
    app.logger.info(f"get_projects - identity: {identity}")
    
    # Admin sees all projects, regular users see only their own projects
    if identity.get('is_admin', False):
        # Admin sees all projects
        projects = Project.query.order_by(Project.created_at.desc()).all()
    else:
        # Regular users see only projects they own
        user_id = identity.get('user_id')
        if user_id:
            projects = Project.query.filter(Project.owner_id == user_id).order_by(Project.created_at.desc()).all()
        else:
            projects = []
    
    project_data = []
    for project in projects:
        # Count conversations for this project (filtered by user if not admin)
        if identity.get('is_admin', False):
            conversation_count = db.session.query(Conversation).filter(
                Conversation.project_id == project.id
            ).count()
        else:
            conversation_count = db.session.query(Conversation).filter(
                Conversation.project_id == project.id,
                Conversation.user_id == identity.get('user_id')
            ).count()
        
        project_data.append({
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat() if project.updated_at else None,
            'conversation_count': conversation_count
        })
    
    return jsonify(project_data)

@app.route('/projects', methods=['POST'])
def create_project():
    from models import Project
    import json
    
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Project name is required'}), 400
    
    # Get user identity for ownership
    identity = get_user_identity()
    owner_id = identity['user_id']
    
    # Convert step and rule arrays to JSON strings for storage
    goal_steps = data.get('goal_steps', [])
    if isinstance(goal_steps, str):
        # If it's a string with line breaks, split into array
        goal_steps = [step.strip() for step in goal_steps.split('\n') if step.strip()]
    
    rules_do = data.get('rules_do', [])
    if isinstance(rules_do, str):
        rules_do = [rule.strip() for rule in rules_do.split('\n') if rule.strip()]
        
    rules_dont = data.get('rules_dont', [])
    if isinstance(rules_dont, str):
        rules_dont = [rule.strip() for rule in rules_dont.split('\n') if rule.strip()]
    
    project = Project(
        name=data['name'],
        description=data.get('description', ''),
        agent_name=data.get('agent_name'),
        agent_role=data.get('agent_role'),
        agent_personality=data.get('agent_personality'),
        primary_goal=data.get('primary_goal'),
        goal_steps=json.dumps(goal_steps) if goal_steps else None,
        rules_do=json.dumps(rules_do) if rules_do else None,
        rules_dont=json.dumps(rules_dont) if rules_dont else None,
        context_background=data.get('context_background'),
        user_role=data.get('user_role'),
        output_format=data.get('output_format'),
        persona_id=data.get('persona_id'),
        # Math-specific fields
        math_level=data.get('math_level'),
        math_subject=data.get('math_subject'),
        learning_style=data.get('learning_style'),
        difficulty_preference=data.get('difficulty_preference'),
        owner_id=owner_id
    )
    
    db.session.add(project)
    db.session.commit()
    
    # Return project data including template fields
    response_data = {
        'id': str(project.id),
        'name': project.name,
        'description': project.description,
        'created_at': project.created_at.isoformat(),
        'updated_at': project.updated_at.isoformat() if project.updated_at else None
    }
    
    # Include template data if present
    if project.agent_name or project.agent_role or project.primary_goal:
        response_data['template'] = {
            'agent_name': project.agent_name,
            'agent_role': project.agent_role,
            'agent_personality': project.agent_personality,
            'primary_goal': project.primary_goal,
            'goal_steps': json.loads(project.goal_steps) if project.goal_steps else [],
            'rules_do': json.loads(project.rules_do) if project.rules_do else [],
            'rules_dont': json.loads(project.rules_dont) if project.rules_dont else [],
            'context_background': project.context_background,
            'user_role': project.user_role,
            'output_format': project.output_format
        }
    
    return jsonify(response_data), 201

@app.route('/api/projects/<project_id>', methods=['GET'])
@auth.login_required
def get_project(project_id):
    """Get individual project details"""
    try:
        app.logger.info(f"Getting project {project_id}")
        project_uuid = uuid.UUID(project_id)
        project = Project.query.get_or_404(project_uuid)
        app.logger.info(f"Found project: {project.name}")
        
        # Check if user has access to this project
        current_user_id = get_user_identity()['user_id']
        app.logger.info(f"Current user ID: {current_user_id} (type: {type(current_user_id)}), Project owner ID: {project.owner_id} (type: {type(project.owner_id)})")
        
        # Convert both to strings for comparison
        current_user_str = str(current_user_id)
        project_owner_str = str(project.owner_id)
        app.logger.info(f"Comparing: '{current_user_str}' == '{project_owner_str}'")
        
        if project_owner_str != current_user_str:
            app.logger.warning(f"Access denied for user {current_user_id} to project {project_id}")
            return jsonify({'error': 'Access denied'}), 403
        
        try:
            app.logger.info(f"🔍 Backend debugging - project.name: '{project.name}' (type: {type(project.name)})")
            project_data = {
                'id': str(project.id),
                'name': project.name or '',
                'description': project.description or '',
                'agent_name': project.agent_name or '',
                'agent_role': project.agent_role or '',
                'agent_personality': project.agent_personality or '',
                'primary_goal': project.primary_goal or '',
                'goal_steps': project.goal_steps or '',
                'rules_do': project.rules_do or '',
                'rules_dont': project.rules_dont or '',
                'context_background': project.context_background or '',
                'user_role': project.user_role or '',
                'output_format': project.output_format or '',
                'math_level': project.math_level or '',
                'math_subject': project.math_subject or '',
                'learning_style': project.learning_style or '',
                'difficulty_preference': project.difficulty_preference or '',
                'persona_id': str(project.persona_id) if project.persona_id else None,
                'created_at': project.created_at.isoformat() if project.created_at else None,
                'updated_at': project.updated_at.isoformat() if project.updated_at else None
            }
            
            app.logger.info(f"Returning project data for {project.name}")
            return jsonify({
                'success': True,
                'project': project_data
            })
        except Exception as e:
            app.logger.error(f"Error creating project data: {str(e)}")
            return jsonify({'error': 'Failed to create project data'}), 500
        
    except ValueError as e:
        app.logger.error(f"Invalid project ID {project_id}: {str(e)}")
        return jsonify({'error': 'Invalid project ID'}), 400
    except Exception as e:
        app.logger.error(f"Error getting project {project_id}: {str(e)}")
        return jsonify({'error': 'Failed to get project'}), 500

@app.route('/projects/<project_id>/template', methods=['GET'])
@auth.login_required
def get_project_template(project_id):
    """Get project template data"""
    try:
        conv_uuid = uuid.UUID(project_id)
        project = Project.query.get_or_404(conv_uuid)
        
        import json
        template_data = {
            'agent_name': project.agent_name,
            'agent_role': project.agent_role,
            'agent_personality': project.agent_personality,
            'primary_goal': project.primary_goal,
            'goal_steps': json.loads(project.goal_steps) if project.goal_steps else [],
            'rules_do': json.loads(project.rules_do) if project.rules_do else [],
            'rules_dont': json.loads(project.rules_dont) if project.rules_dont else [],
            'context_background': project.context_background,
            'user_role': project.user_role,
            'output_format': project.output_format,
            'persona_id': str(project.persona_id) if project.persona_id else None,
            # Math-specific fields
            'math_level': project.math_level,
            'math_subject': project.math_subject,
            'learning_style': project.learning_style,
            'difficulty_preference': project.difficulty_preference
        }
        
        return jsonify({
            'project': {
                'id': str(project.id),
                'name': project.name,
                'description': project.description
            },
            'template': template_data
        }), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid project ID'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/projects/<project_id>/profile', methods=['PUT'])
@auth.login_required
def update_project_profile(project_id):
    """Update project profile information (name, description, persona, etc.)"""
    try:
        project_uuid = uuid.UUID(project_id)
        project = Project.query.get_or_404(project_uuid)
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update project fields - use correct field names that match the Project model
        if 'name' in data:
            project.name = data['name'].strip()
        
        if 'description' in data:
            project.description = data['description'].strip()
        
        if 'agent_name' in data:
            project.agent_name = data['agent_name'].strip()
        
        if 'agent_role' in data:
            project.agent_role = data['agent_role'].strip()
        
        if 'agent_personality' in data:
            project.agent_personality = data['agent_personality'].strip()
        
        if 'primary_goal' in data:
            project.primary_goal = data['primary_goal'].strip()
        
        if 'context_background' in data:
            project.context_background = data['context_background'].strip()
        
        if 'user_role' in data:
            project.user_role = data['user_role'].strip()
        
        if 'output_format' in data:
            project.output_format = data['output_format'].strip()
        
        if 'math_level' in data:
            project.math_level = data['math_level'].strip()
        
        if 'math_subject' in data:
            project.math_subject = data['math_subject'].strip()
        
        if 'learning_style' in data:
            project.learning_style = data['learning_style'].strip()
        
        if 'difficulty_preference' in data:
            project.difficulty_preference = data['difficulty_preference'].strip()
        
        if 'persona_id' in data:
            project.persona_id = data['persona_id'] if data['persona_id'] else None
        
        # Update timestamp
        from datetime import datetime
        project.updated_at = datetime.utcnow()
        
        app.logger.info(f"Updating project {project.name} with data: {data}")
        
        try:
            db.session.commit()
            app.logger.info(f"Successfully updated project {project.name}")
            
            return jsonify({
                'success': True,
                'message': 'Project profile updated successfully',
                'project': {
                    'id': str(project.id),
                    'name': project.name,
                    'description': project.description,
                    'agent_name': project.agent_name,
                    'agent_role': project.agent_role,
                    'agent_personality': project.agent_personality,
                    'primary_goal': project.primary_goal,
                    'context_background': project.context_background,
                    'user_role': project.user_role,
                    'output_format': project.output_format,
                    'math_level': project.math_level,
                    'math_subject': project.math_subject,
                    'learning_style': project.learning_style,
                    'difficulty_preference': project.difficulty_preference,
                    'persona_id': str(project.persona_id) if project.persona_id else None
                }
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Database error updating project {project.name}: {str(e)}")
            return jsonify({'error': 'Database error updating project'}), 500
        
    except ValueError:
        return jsonify({'error': 'Invalid project ID'}), 400
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating project profile: {str(e)}")
        return jsonify({'error': 'Failed to update project profile'}), 500

@csrf.exempt
@app.route('/projects/<project_id>/template', methods=['PUT'])
@auth.login_required
def update_project_template(project_id):
    """Update project template data"""
    try:
        conv_uuid = uuid.UUID(project_id)
        project = Project.query.get_or_404(conv_uuid)
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        import json
        
        # Convert step and rule arrays to JSON strings for storage
        goal_steps = data.get('goal_steps', [])
        if isinstance(goal_steps, str):
            goal_steps = [step.strip() for step in goal_steps.split('\n') if step.strip()]
        
        rules_do = data.get('rules_do', [])
        if isinstance(rules_do, str):
            rules_do = [rule.strip() for rule in rules_do.split('\n') if rule.strip()]
            
        rules_dont = data.get('rules_dont', [])
        if isinstance(rules_dont, str):
            rules_dont = [rule.strip() for rule in rules_dont.split('\n') if rule.strip()]
        
        # Update template fields
        project.agent_name = data.get('agent_name')
        project.agent_role = data.get('agent_role')
        project.agent_personality = data.get('agent_personality')
        project.primary_goal = data.get('primary_goal')
        project.goal_steps = json.dumps(goal_steps) if goal_steps else None
        project.rules_do = json.dumps(rules_do) if rules_do else None
        project.rules_dont = json.dumps(rules_dont) if rules_dont else None
        project.context_background = data.get('context_background')
        project.user_role = data.get('user_role')
        project.output_format = data.get('output_format')
        project.persona_id = data.get('persona_id')
        # Math-specific fields
        project.math_level = data.get('math_level')
        project.math_subject = data.get('math_subject')
        project.learning_style = data.get('learning_style')
        project.difficulty_preference = data.get('difficulty_preference')
        project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Project template updated successfully'
        }), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid project ID'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project and optionally delete or unassign related conversations"""
    try:
        from models import Project, Conversation, ContextItem, LLMUsageLog, LLMErrorLog
        
        app.logger.info(f"Attempting to delete project: {project_id}")
        
        project = Project.query.get(project_id)
        if not project:
            app.logger.error(f"Project not found: {project_id}")
            return jsonify({'error': 'Project not found'}), 404
        
        # Check if we should delete conversations too
        delete_conversations = request.args.get('delete_conversations', 'false').lower() == 'true'
        app.logger.info(f"Delete conversations flag: {delete_conversations}")
        
        # Get conversation count and IDs before any operations
        conversations = Conversation.query.filter_by(project_id=project_id).all()
        conversation_count = len(conversations)
        conversation_ids = [conv.id for conv in conversations]
        app.logger.info(f"Found {conversation_count} conversations associated with project: {conversation_ids}")
        
        if delete_conversations:
            # Need to handle foreign key constraints before deleting conversations
            if conversation_ids:
                # Delete LLM usage logs that reference these conversations
                usage_logs_deleted = LLMUsageLog.query.filter(LLMUsageLog.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
                app.logger.info(f"Deleted {usage_logs_deleted} LLM usage log entries")
                
                # Delete LLM error logs that reference these conversations  
                error_logs_deleted = LLMErrorLog.query.filter(LLMErrorLog.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
                app.logger.info(f"Deleted {error_logs_deleted} LLM error log entries")
                
                # Delete any context sessions that reference these conversations
                try:
                    from models import ContextSession
                    context_sessions_deleted = ContextSession.query.filter(ContextSession.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
                    app.logger.info(f"Deleted {context_sessions_deleted} context session entries")
                except Exception as ctx_error:
                    app.logger.warning(f"Could not delete context sessions: {ctx_error}")
                
                db.session.flush()  # Apply deletions before proceeding
            
            # Let the cascade relationship handle conversation deletion
            # The Project model has cascade='all, delete-orphan' so conversations will be deleted automatically
            app.logger.info(f"Will delete project {project_id} and let cascade delete {conversation_count} conversations")
            message = f'Project and {conversation_count} conversation{"s" if conversation_count != 1 else ""} deleted'
        else:
            # Unassign conversations from project before deleting project
            # This prevents the cascade from deleting them
            try:
                updated_rows = Conversation.query.filter_by(project_id=project_id).update({'project_id': None})
                db.session.flush()  # Ensure the update is applied before deleting project
                app.logger.info(f"Updated {updated_rows} conversations to unassign from project")
            except Exception as update_error:
                app.logger.error(f"Error updating conversations: {str(update_error)}")
                raise update_error
            
            app.logger.info(f"Deleting project {project_id}, unassigned {conversation_count} conversations")
            message = f'Project deleted, {conversation_count} conversation{"s" if conversation_count != 1 else ""} unassigned'
        
        # Handle context items - they have ondelete='SET NULL' so they'll be handled automatically
        context_items_count = ContextItem.query.filter_by(project_id=project_id).count()
        if context_items_count > 0:
            app.logger.info(f"Found {context_items_count} context items that will be unassigned from project")
        
        # Delete the project
        try:
            app.logger.info(f"About to delete project: {project.name} ({project.id})")
            db.session.delete(project)
            db.session.commit()
            app.logger.info(f"Successfully deleted project: {project_id}")
        except Exception as delete_error:
            app.logger.error(f"Error deleting project: {str(delete_error)}")
            raise delete_error
        
        return jsonify({'success': True, 'message': message}), 200
        
    except Exception as e:
        app.logger.error(f"Error deleting project {project_id}: {str(e)}")
        app.logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        app.logger.error(f"Traceback: {traceback.format_exc()}")
        
        db.session.rollback()
        return jsonify({'error': f'Failed to delete project: {str(e)}'}), 500

@csrf.exempt
@app.route('/api/generate-followup-questions', methods=['POST'])
@auth.access_required(allow_free=True)
def generate_followup_questions():
    """Generate contextually relevant follow-up questions based on the latest AI response"""
    try:
        data = request.get_json()
        if not data or not data.get('latest_response'):
            app.logger.warning("Follow-up questions: Missing latest_response")
            return jsonify({'error': 'Latest response is required'}), 400
        
        latest_response = data['latest_response']
        model = data.get('model', 'gpt-3.5-turbo')
        project_id = data.get('project_id')
        conversation_id = data.get('conversation_id')
        is_math_project = data.get('is_math_project', False)
        
        # Try to determine if this is a math project
        # First, check the frontend's is_math_project flag
        if not is_math_project and (project_id or conversation_id):
            try:
                from models import Project, Conversation
                import uuid
                
                # Try to get project from conversation if we have conversation_id
                if conversation_id and not project_id:
                    try:
                        conv_uuid = uuid.UUID(conversation_id)
                        conversation = Conversation.query.get(conv_uuid)
                        if conversation and conversation.project_id:
                            project_id = str(conversation.project_id)
                    except Exception as e:
                        app.logger.debug(f"Could not get project from conversation: {e}")
                
                # Now check if the project has math fields
                if project_id:
                    try:
                        project_uuid = uuid.UUID(project_id)
                        project = Project.query.get(project_uuid)
                        if project:
                            is_math_project = bool(project.math_level or project.math_subject)
                            app.logger.info(f"Detected math project from DB: math_level={project.math_level}, math_subject={project.math_subject}")
                    except Exception as e:
                        app.logger.debug(f"Could not fetch project from DB: {e}")
            except Exception as e:
                app.logger.debug(f"Could not determine if math project: {e}")
        
        app.logger.info(f"Generating follow-up questions using model: {model}, is_math: {is_math_project}")
        
        # Create a focused prompt for generating follow-up questions based only on the latest response
        system_prompt = """You are an expert at generating relevant follow-up questions. Based ONLY on the AI response provided, generate exactly 3 highly relevant, specific follow-up questions that would naturally continue the conversation.

The questions should:
1. Be directly related to the content of this specific response
2. Help the user dive deeper into the topic or explore related aspects
3. Be actionable and lead to meaningful responses
4. Avoid generic questions like "Can you tell me more?"
5. Be concise and clear (under 15 words each)
6. Focus on practical next steps, clarifications, or related topics

Return only the 3 questions, one per line, without numbering or bullet points."""

        # Create the prompt for generating questions - only using the latest response
        followup_messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f"Generate 3 relevant follow-up questions for this AI response:\n\n{latest_response}"}
        ]
        
        # Get follow-up questions from AI
        from llm_service import LLMService
        llm_service = LLMService()
        
        ai_response, tokens, estimated_cost = llm_service.get_response(
            model, 
            followup_messages, 
            max_tokens=150,  # Keep it short
            temperature=0.9  # Increased for more variety
        )
        
        app.logger.info(f"Follow-up AI response: {ai_response}")
        
        # Parse the response into individual questions
        questions = []
        if ai_response:
            lines = ai_response.strip().split('\n')
            for line in lines:
                question = line.strip()
                # Remove numbering, bullets, and clean up
                question = question.lstrip('123456789.-• ')
                if question and len(question) > 5:  # Basic validation
                    questions.append(question)
        
        app.logger.info(f"Parsed {len(questions)} questions from AI response")
        
        # Ensure we have exactly 3 questions, pad with fallbacks if needed
        while len(questions) < 3:
            fallback_questions = [
                "What would you recommend as the next step?",
                "Can you elaborate on this approach?", 
                "How would this work in practice?"
            ]
            for fallback in fallback_questions:
                if fallback not in questions and len(questions) < 3:
                    questions.append(fallback)
                    app.logger.info(f"Added fallback question: {fallback}")
        
        # Return only first 3 questions
        questions = questions[:3]
        
        # For math projects, add 2 additional math-specific questions
        if is_math_project:
            math_specific_questions = [
                "Explain this to me as if I was 2 years younger",
                "Give me a practical, real-world example"
            ]
            questions.extend(math_specific_questions)
            app.logger.info(f"Added {len(math_specific_questions)} math-specific questions - total now {len(questions)}")
        
        app.logger.info(f"Returning follow-up questions: {questions}")
        return jsonify({'questions': questions}), 200
        
    except Exception as e:
        app.logger.error(f"Error generating follow-up questions: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        # Return fallback questions on error
        fallback_questions = [
            "Can you explain this further?",
            "What should I consider next?",
            "How does this apply to my situation?"
        ]
        return jsonify({'questions': fallback_questions}), 200

@csrf.exempt
@app.route('/projects/<project_id>', methods=['PATCH'])
def rename_project(project_id):
    """Rename/update a project"""
    try:
        from models import Project
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': 'Project name is required'}), 400
        
        project.name = data['name']
        if 'description' in data:
            project.description = data['description']
        
        db.session.commit()
        
        return jsonify({
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat() if project.updated_at else None
        }), 200
    except Exception as e:
        app.logger.error(f"Error renaming project: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to rename project'}), 500

@app.route('/conversations', methods=['GET'])
def get_conversations():
    """Get conversations filtered by current user (authenticated or free user)"""
    project_id = request.args.get('project_id')
    
    # Start with base query filtered by user
    query = filter_conversations_by_user(Conversation.query)
    
    # Add project filter if specified
    if project_id:
        query = query.filter_by(project_id=project_id)
    
    conversations = query.order_by(Conversation.updated_at.desc()).all()
    
    # Set session cookie for free users if needed
    identity = get_user_identity()
    response_data = [
        {
            'id': str(conv.id),
            'project_id': str(conv.project_id) if conv.project_id else None,
            'title': conv.title,
            'llm_model': conv.llm_model,
            'created_at': conv.created_at.isoformat(),
            'updated_at': conv.updated_at.isoformat(),
            'tags': conv.tags or [],
            'message_count': len(conv.messages),
            'attachment_count': len(conv.context_documents) if conv.context_documents else 0
        }
        for conv in conversations
    ]
    
    response = jsonify(response_data)
    
    # Set session cookie for free users
    if identity['type'] == 'free' and identity['session_id'] and not request.cookies.get('session_id'):
        response.set_cookie('session_id', identity['session_id'], max_age=30*24*60*60)  # 30 days
    
    return response

# Update create_conversation to accept project_id
@csrf.exempt
@app.route('/conversations', methods=['POST'])
def create_conversation():
    """Create a new conversation with proper user ownership"""
    data = request.get_json()
    if not data or not data.get('title') or not data.get('llm_model'):
        return jsonify({'error': 'Title and llm_model are required'}), 400
    
    # Get user identity for ownership
    identity = get_user_identity()
    
    app.logger.info(f"Creating conversation - identity: {identity}")
    
    # user_id is stored as string (VARCHAR in database)
    user_id = identity['user_id']
    
    from models import Conversation
    conversation = Conversation(
        title=data['title'],
        llm_model=data['llm_model'],
        tags=data.get('tags', []),
        project_id=data.get('project_id'),
        user_id=user_id,
        session_id=identity['session_id'],
        ip_address=None  # IP address not needed for access control with unified identity system
    )
    
    app.logger.info(f"Conversation user_id set to: {conversation.user_id}")
    db.session.add(conversation)
    db.session.commit()
    
    response_data = {
        'id': str(conversation.id),
        'title': conversation.title,
        'llm_model': conversation.llm_model,
        'created_at': conversation.created_at.isoformat(),
        'tags': conversation.tags
    }
    
    response = jsonify(response_data)
    
    # Set session cookie for free users
    if identity['type'] == 'free' and identity['session_id'] and not request.cookies.get('session_id'):
        response.set_cookie('session_id', identity['session_id'], max_age=30*24*60*60)  # 30 days
    
    return response, 201

@app.route('/conversations/<conversation_id>/messages', methods=['GET'])
@require_conversation_access
def get_messages(conversation_id):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        return jsonify({'error': 'Invalid conversation ID'}), 400
    
    conversation = Conversation.query.get_or_404(conv_uuid)
    messages = Message.query.filter_by(conversation_id=conv_uuid).order_by(Message.timestamp.asc()).all()
    
    return jsonify({
        'conversation': {
            'id': str(conversation.id),
            'title': conversation.title,
            'llm_model': conversation.llm_model,
            'project_id': str(conversation.project_id) if conversation.project_id else None,
            'context_documents': conversation.context_documents or []
        },
        'messages': [{
            'id': str(msg.id),
            'role': msg.role,
            'content': msg.content,
            'timestamp': msg.timestamp.isoformat()
        } for msg in messages]
    })

@app.route('/conversations/<conversation_id>', methods=['PUT'])
@require_conversation_access
def update_conversation(conversation_id):
    """Update conversation details (title, etc.)"""
    try:
        conv_uuid = uuid.UUID(conversation_id)
        
        conversation = Conversation.query.get(conv_uuid)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update title if provided
        if 'title' in data:
            new_title = data['title'].strip()
            if not new_title:
                return jsonify({'error': 'Title cannot be empty'}), 400
            conversation.title = new_title
        
        # Update timestamp
        conversation.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Conversation updated successfully',
            'conversation': {
                'id': str(conversation.id),
                'title': conversation.title,
                'updated_at': conversation.updated_at.isoformat()
            }
        }), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid conversation ID'}), 400
    except Exception as e:
        app.logger.error(f"Error updating conversation: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update conversation'}), 500

@app.route('/conversations/<conversation_id>', methods=['DELETE'])
@require_conversation_access
def delete_conversation(conversation_id):
    """Delete a conversation and all its related records"""
    try:
        conv_uuid = uuid.UUID(conversation_id)
        
        conversation = Conversation.query.get(conv_uuid)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        app.logger.info(f"Attempting to delete conversation: {conversation_id}")
        
        # Delete related records that reference this conversation to avoid foreign key constraints
        from models import LLMUsageLog, LLMErrorLog
        
        # Delete LLM usage logs
        usage_logs_deleted = LLMUsageLog.query.filter_by(conversation_id=conv_uuid).delete()
        app.logger.info(f"Deleted {usage_logs_deleted} LLM usage log entries for conversation {conversation_id}")
        
        # Delete LLM error logs  
        error_logs_deleted = LLMErrorLog.query.filter_by(conversation_id=conv_uuid).delete()
        app.logger.info(f"Deleted {error_logs_deleted} LLM error log entries for conversation {conversation_id}")
        
        # Delete context sessions that reference this conversation
        try:
            from models import ContextSession
            context_sessions_deleted = ContextSession.query.filter_by(conversation_id=conv_uuid).delete()
            app.logger.info(f"Deleted {context_sessions_deleted} context session entries for conversation {conversation_id}")
        except Exception as ctx_error:
            app.logger.warning(f"Could not delete context sessions for conversation {conversation_id}: {ctx_error}")
        
        # Delete context usage logs that reference this conversation
        try:
            from models import ContextUsageLog
            context_usage_deleted = ContextUsageLog.query.filter_by(conversation_id=conv_uuid).delete()
            app.logger.info(f"Deleted {context_usage_deleted} context usage log entries for conversation {conversation_id}")
        except Exception as ctx_usage_error:
            app.logger.warning(f"Could not delete context usage logs for conversation {conversation_id}: {ctx_usage_error}")
        
        # Apply all the deletions before deleting the conversation
        db.session.flush()
        
        # Now delete the conversation (messages will be cascade deleted)
        db.session.delete(conversation)
        db.session.commit()
        
        app.logger.info(f"Successfully deleted conversation: {conversation_id}")
        return jsonify({'success': True, 'message': 'Conversation deleted'}), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid conversation ID'}), 400
    except Exception as e:
        app.logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
        app.logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        app.logger.error(f"Traceback: {traceback.format_exc()}")
        
        db.session.rollback()
        return jsonify({'error': f'Failed to delete conversation: {str(e)}'}), 500

@csrf.exempt
@app.route('/conversations/<conversation_id>/messages', methods=['POST'])
@require_conversation_access
def add_message(conversation_id):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        return jsonify({'error': 'Invalid conversation ID'}), 400
    
    conversation = Conversation.query.get_or_404(conv_uuid)
    data = request.get_json()
    
    if not data or not data.get('role') or not data.get('content'):
        return jsonify({'error': 'Role and content are required'}), 400
    
    if data['role'] not in ['user', 'assistant']:
        return jsonify({'error': 'Role must be user or assistant'}), 400
    
    message = Message(
        conversation_id=conv_uuid,
        role=data['role'],
        content=data['content']
    )
    
    conversation.updated_at = datetime.utcnow()
    
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'id': str(message.id),
        'role': message.role,
        'content': message.content,
        'timestamp': message.timestamp.isoformat()
    }), 201

@csrf.exempt
def fetch_nsw_math_curriculum_content():
    """Fetch NSW Mathematics K-10 curriculum content for math context"""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        url = "https://curriculum.nsw.edu.au/learning-areas/mathematics/mathematics-k-10-2022/overview"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        session = requests.Session()
        session.headers.update(headers)
        
        try:
            response = session.get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
        except requests.exceptions.SSLError:
            response = session.get(url, timeout=15, allow_redirects=True, verify=False)
            response.raise_for_status()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if url.startswith('https://'):
                http_url = url.replace('https://', 'http://', 1)
                response = session.get(http_url, timeout=15, allow_redirects=True)
                response.raise_for_status()
            else:
                raise
        
        # Parse HTML and extract text
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text content
        content = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in content.splitlines())
        content = '\n'.join(line for line in lines if line)
        
        # Limit content length to avoid token limits
        if len(content) > 8000:
            content = content[:8000] + "..."
        
        app.logger.info(f"Successfully fetched NSW Math curriculum content ({len(content)} chars)")
        return content
        
    except Exception as e:
        app.logger.error(f"Error fetching NSW Math curriculum content: {str(e)}")
        return None

def is_math_question(message):
    """Check if the message is a math-related question"""
    math_keywords = [
        'math', 'mathematics', 'calculate', 'solve', 'equation', 'formula', 'algebra',
        'geometry', 'trigonometry', 'calculus', 'statistics', 'probability', 'fraction',
        'decimal', 'percentage', 'addition', 'subtraction', 'multiplication', 'division',
        'number', 'numbers', 'problem', 'sum', 'difference', 'product', 'quotient',
        'angle', 'triangle', 'circle', 'square', 'rectangle', 'area', 'perimeter',
        'volume', 'surface area', 'graph', 'plot', 'coordinate', 'axis', 'slope',
        'gradient', 'function', 'variable', 'unknown', 'solve for', 'find the value',
        'what is', 'how many', 'how much', 'nsw curriculum', 'stage', 'year level'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in math_keywords)

@app.route('/test-script')
def test_script():
    """Test route to verify script file is accessible"""
    try:
        import os
        script_path = os.path.join(app.static_folder, 'js', 'project_setup_modal.js')
        if os.path.exists(script_path):
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"Script exists and is {len(content)} characters long. First 200 chars: {content[:200]}"
        else:
            return f"Script not found at: {script_path}"
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/chat', methods=['POST'])
@limiter.limit("30 per minute")
@auth.access_required(allow_free=True)
def chat():
    try:
        data = request.get_json()
        
        if not data or not data.get('message') or not data.get('model'):
            return jsonify({'error': 'Message and model are required'}), 400
        
        conversation_id = data.get('conversation_id')
        user_message = data['message']
        model = data['model']
        project_id = data.get('project_id')  # Get project_id for new conversations
        
        # Handle free tier access
        if getattr(request, 'access_type', None) == 'free_tier':
            from auth import FreeAccessManager
            free_info = FreeAccessManager.log_free_query(model)
            app.logger.info(f"Free tier chat: model={model}, remaining={free_info['queries_remaining']}")
        
        app.logger.info(f"Chat request: model={model}, message_length={len(user_message)}")
        
        # Get conversation history if conversation exists
        messages = []
        
        # Add project template as system prompt if available (for both existing and new conversations)
        project = None
        if conversation_id:
            conv_uuid = uuid.UUID(conversation_id)
            conversation = Conversation.query.get_or_404(conv_uuid)
            
            # Get project from existing conversation
            if conversation.project_id:
                project = Project.query.get(conversation.project_id)
        elif project_id:
            # For new conversations, get project directly
            try:
                project_uuid = uuid.UUID(project_id)
                project = Project.query.get(project_uuid)
            except (ValueError, TypeError):
                app.logger.warning(f"Invalid project_id format: {project_id}")
        
        # Get user's display name for personalized responses
        user_display_name = session.get('display_name') or session.get('username') or 'User'
        
        # Apply project template if we have a project
        if project:
            project_system_prompt = build_project_system_prompt(project)
            if project_system_prompt:
                # Add personalization instruction
                personalized_prompt = f"{project_system_prompt}\n\nNote: You are assisting {user_display_name}. Address them naturally by name in your responses when appropriate."
                messages.append({
                    'role': 'system',
                    'content': personalized_prompt
                })
                app.logger.info(f"Applied project template for project: {project.name}")
        else:
            # Add a default personalized system prompt if no project
            messages.append({
                'role': 'system',
                'content': f"You are a helpful AI assistant. You are currently assisting {user_display_name}. Address them naturally by name in your responses when appropriate, making the conversation feel personal and engaging."
            })
        
        # Load conversation history if conversation exists
        if conversation_id:
            db_messages = Message.query.filter_by(conversation_id=conv_uuid).order_by(Message.timestamp.asc()).all()
            conversation_messages = llm_service.format_conversation_for_llm(db_messages)
            messages.extend(conversation_messages)
            # Add context items to prompt using new context management system
            try:
                active_context = ContextService.get_conversation_context(str(conversation_id))
                if active_context:
                    # Build comprehensive context system message
                    context_content = []
                    for ctx in active_context:
                        context_content.append(f"""
=== {ctx['name']} ===
Type: {ctx['content_type']}
{f"Description: {ctx['description']}" if ctx['description'] else ""}

{ctx['content_text']}
""")
                    
                    if context_content:
                        system_msg = f"""You have access to the following context documents for this conversation. Use this information to inform your responses:

{chr(10).join(context_content)}

---
Please use this context information appropriately when responding to user questions. If the user asks you to create content based on guidelines, use the provided guidelines. If they ask about document content, reference the documents above."""
                        
                        messages.insert(0, {
                            'role': 'system',
                            'content': system_msg
                        })
                        
                        app.logger.info(f"Added {len(active_context)} context items to conversation {conversation_id}")
                    
            except Exception as context_error:
                app.logger.error(f"Failed to load context for conversation {conversation_id}: {context_error}")
        
        # Add NSW Math curriculum content for Math projects
        # Check if project has a persona with 'math' category OR has math-specific fields set
        is_math_project = False
        if project:
            if project.persona and hasattr(project.persona, 'category') and 'math' in project.persona.category.lower():
                is_math_project = True
            elif project.math_level or project.math_subject:
                is_math_project = True
        
        if is_math_project:
            app.logger.info(f"Math project detected ({project.name}), loading math curriculum from database")
            
            # Load math curriculum context items from database
            from models import ContextItem
            math_context_items = ContextItem.query.filter(
                ContextItem.user_id == 'system',
                ContextItem.is_active == True,
                ContextItem.extra_data['category'].astext == 'math'
            ).all()
            
            if math_context_items:
                math_context_parts = []
                for item in math_context_items:
                    math_context_parts.append(f"### {item.name}\n\n{item.content_text}")
                
                math_context_msg = f"""NSW Mathematics K-10 Curriculum Context:

You have access to the official NSW Mathematics K-10 Syllabus (2022) content and related learning resources. Use this information to provide educationally appropriate responses that align with NSW educational standards and stage-appropriate content.

{''.join(math_context_parts)}

---
When responding to math questions, please:
1. Reference appropriate NSW curriculum stages (Early Stage 1, Stage 1, Stage 2, Stage 3, Stage 4, Stage 5) when relevant
2. Use curriculum-appropriate terminology and concepts
3. Ensure explanations align with NSW educational standards
4. Consider the Working mathematically processes: communicating, understanding and fluency, reasoning, and problem solving
5. Reference the three content areas: Number and algebra, Measurement and space, Statistics and probability when applicable"""
                
                messages.insert(0, {
                    'role': 'system',
                    'content': math_context_msg
                })
                app.logger.info(f"Added {len(math_context_items)} math curriculum context item(s) from database to Math project")
            else:
                app.logger.warning("No math curriculum context items found in database")
        
        # Fallback to old context_documents system for backward compatibility
        import json
        docs = getattr(conversation, 'context_documents', None)
        if isinstance(docs, str):
            try:
                docs = json.loads(docs)
            except Exception:
                docs = []
        if docs and not active_context:  # Only use old system if new system has no context
            for doc in docs:
                if doc and 'content' in doc:
                    task_type = doc.get('task_type', 'instructions')
                    filename = doc.get('filename', 'uploaded file')
                    content = doc['content']
                    
                    if task_type == 'summary':
                        system_msg = f"You have been provided with a document ({filename}) to summarize. You can analyze, count words, and provide detailed summaries of this content:\n\n{content}"
                    elif task_type == 'analysis':
                        system_msg = f"You have been provided with a document ({filename}) to analyze. You can examine, count words, and provide detailed analysis of this content:\n\n{content}"
                    else:
                        system_msg = f"Document reference ({filename}): You have access to this document content and can answer questions about it, count words, analyze it, or use it as guidelines:\n\n{content}"
                    
                    messages.insert(0, {
                        'role': 'system',
                        'content': system_msg
                    })
        
        # Add user message
        messages.append({
            'role': 'user',
            'content': user_message
        })
        
        # Log prompt details
        app.logger.debug(f"LLM request with {len(messages)} messages for model {model}")
        
        # Resolve model identifier for API call
        # The 'model' parameter is the display name from the UI
        # We need to get the actual API model identifier (model_value)
        model_identifier = get_model_identifier(model)
        app.logger.info(f"Resolved model '{model}' to identifier '{model_identifier}'")
        
        # Check if user is authenticated (not free tier)
        is_authenticated = getattr(request, 'access_type', None) != 'free_tier'
        
        app.logger.info(f"Calling LLM service for model: {model} (API id: {model_identifier}), authenticated: {is_authenticated}")
        
        # Get RAG context if available (using simple RAG service until migration is confirmed)
        rag_context = ""
        rag_sources = []
        try:
            from rag_service_simple import SimpleRAGService
            
            # Get user identity for filtering
            identity = get_user_identity()
            user_id = str(identity['user_id']) if identity['user_id'] else None
            
            # Initialize simple RAG service (documents only for now)
            rag_service = SimpleRAGService(
                openai_api_key=os.getenv('OPENAI_API_KEY')
            )
            
            # Get relevant context from documents
            rag_context = rag_service.get_context_for_query(
                query=user_message,
                max_context_length=2000,
                user_id=user_id
            )
            
            if rag_context:
                # Get source details for citation
                search_results = rag_service.search_similar_chunks(
                    query=user_message,
                    user_id=user_id,
                    similarity_threshold=0.6,
                    max_results=3
                )
                
                # Format sources for display
                rag_sources = [{'document': r['document_name'], 'score': r['similarity_score']} for r in search_results]
                
                # Add RAG context to the system prompt
                rag_system_message = f"""
RELEVANT KNOWLEDGE BASE CONTEXT:
{rag_context}

Use this context to provide accurate, detailed responses. When referencing information from the knowledge base, be specific about what you're drawing from. If the context doesn't contain relevant information for the user's question, say so clearly.
"""
                messages.append({
                    'role': 'system',
                    'content': rag_system_message
                })
                
                app.logger.info(f"RAG context retrieved: {len(rag_context)} chars from {len(rag_sources)} sources")
        except Exception as e:
            app.logger.error(f"RAG context retrieval failed: {str(e)}")
            rag_context = ""
            rag_sources = []
        
        # Reject Stability AI image models in chat (they're for image generation only)
        if model_identifier.startswith('stable-image') or model_identifier.startswith('stable-audio'):
            app.logger.error(f"Attempted to use image generation model {model_identifier} for chat")
            return jsonify({'error': f'Model {model} is for image generation only. Use a different model for text responses.'}), 400
        
        # Get AI response and usage info - use model_identifier for API call
        ai_response, tokens, estimated_cost = llm_service.get_response(model_identifier, messages)
        app.logger.info(f"Got response from {model}: {tokens} tokens, cost: ${estimated_cost:.4f}")
        
        # Log usage
        from models import LLMUsageLog
        usage_log = LLMUsageLog(
            model=model,
            conversation_id=conversation_id if conversation_id else None,
            tokens=tokens,
            estimated_cost=estimated_cost
        )
        db.session.add(usage_log)
        
        # Note: Context usage logging will be handled when messages are saved
        # to avoid foreign key constraints with non-existent message IDs
        
        db.session.commit()
        
        # Prepare response
        response_data = {
            'response': ai_response,
            'model': model,
            'timestamp': datetime.utcnow().isoformat(),
            'rag_used': bool(rag_context),
            'rag_sources': rag_sources if rag_context else []
        }
        
        # Add updated free access info if applicable
        if getattr(request, 'access_type', None) == 'free_tier':
            from auth import FreeAccessManager
            updated_free_info = FreeAccessManager.check_free_access()
            response_data['free_access'] = updated_free_info
        
        return jsonify(response_data)
    
    except Exception as e:
        app.logger.error(f"Chat error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']
        app.logger.info(f'Audio transcription request: {audio_file.filename}, Content-Type: {audio_file.content_type}')
        if audio_file.filename == '':
            return jsonify({'error': 'No audio file selected'}), 400

        # Supported formats for Google Speech-to-Text
        SUPPORTED_FORMATS = ['flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm']
        ext = audio_file.filename.rsplit('.', 1)[-1].lower()
        if ext not in SUPPORTED_FORMATS:
            return jsonify({
                'error': f'Unsupported file format: .{ext}. Supported formats: {SUPPORTED_FORMATS}'
            }), 400

        from google.cloud import speech
        import io

        client = speech.SpeechClient()
        audio_content = audio_file.read()
        audio = speech.RecognitionAudio(content=audio_content)

        # Use OGG_OPUS encoding for .ogg and .webm, LINEAR16 for others
        if ext in ['ogg', 'webm']:
            encoding = speech.RecognitionConfig.AudioEncoding.OGG_OPUS
            sample_rate = 48000  # Opus is usually 48000 Hz
        else:
            encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16
            sample_rate = 16000  # Default for LINEAR16

        config = speech.RecognitionConfig(
            encoding=encoding,
            sample_rate_hertz=sample_rate,
            language_code="en-US",
        )

        response = client.recognize(config=config, audio=audio)

        transcription = ''
        for result in response.results:
            transcription += result.alternatives[0].transcript + ' '

        return jsonify({
            'transcription': transcription.strip(),
            'success': True
        })

    except Exception as e:
        app.logger.error(f"Transcription error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/conversations/<conversation_id>/attachments', methods=['POST'])
@require_conversation_access
def upload_attachments(conversation_id):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        return jsonify({'error': 'Invalid conversation ID'}), 400
    conversation = Conversation.query.get_or_404(conv_uuid)
    if 'files' not in request.files:
        return jsonify({'error': 'No files part in the request'}), 400
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    attachments = []
    try:
        for file in files:
            # Validate file
            if not file.filename:
                return jsonify({'error': 'Empty filename not allowed'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'error': f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
            
            if not validate_file_size(file):
                return jsonify({'error': f'File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB'}), 400
            
            filename = sanitize_filename(secure_filename(file.filename))
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            
            # Ensure unique filename
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(file_path):
                filename = f"{base}_{counter}{ext}"
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                counter += 1
            
            file.save(file_path)
            # Create a new message for the attachment (role='user', content='[file upload]')
            message = Message(
                conversation_id=conv_uuid,
                role='user',
                content=f'[File uploaded: {filename}]'
            )
            db.session.add(message)
            db.session.flush()  # Get message.id
            attachment = Attachment(
                message_id=message.id,
                filename=filename,
                content_type=file.content_type,
                file_path=os.path.relpath(file_path, os.getcwd()),
                created_at=datetime.utcnow()  # Ensure created_at is set
            )
            db.session.add(attachment)
            attachments.append({
                'id': str(attachment.id),
                'filename': filename,
                'content_type': file.content_type,
                'file_path': attachment.file_path,
                'created_at': attachment.created_at.isoformat() if hasattr(attachment, 'created_at') else datetime.utcnow().isoformat()
            })
        db.session.commit()
        return jsonify({'attachments': attachments}), 201
    except Exception as e:
        app.logger.error(f"Attachment upload error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def sanitize_content(content):
    """Sanitize extracted content to prevent security issues"""
    if not content:
        return content
    
    # Remove NUL characters that cause database errors
    content = content.replace('\x00', '')
    
    # Limit content size to prevent memory issues
    MAX_CONTENT_SIZE = 5 * 1024 * 1024  # 5MB text limit
    if len(content) > MAX_CONTENT_SIZE:
        content = content[:MAX_CONTENT_SIZE] + "\n\n[Content truncated for security...]"
    
    # Remove potentially malicious patterns
    content = html.escape(content)  # Escape HTML entities
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'<iframe[^>]*>.*?</iframe>', '', content, flags=re.DOTALL | re.IGNORECASE)
    
    # Clean up excessive whitespace
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    content = content.strip()
    
    return content

def extract_document_content(file, filename):
    """Generic document content extractor - supports PDF, DOCX, TXT, MD, CSV"""
    ext = filename.rsplit('.', 1)[-1].lower()
    content = ''
    
    try:
        if ext == 'pdf':
            reader = PdfReader(file)
            content = '\n'.join(page.extract_text() or '' for page in reader.pages)
        elif ext in ['docx', 'doc'] and DocxDocument:
            doc = DocxDocument(file)
            content = '\n'.join([p.text for p in doc.paragraphs])
        elif ext in ['txt', 'md', 'csv']:
            content = file.read().decode('utf-8', errors='ignore')
        else:
            raise ValueError(f'Unsupported file type: .{ext}')
    except Exception as e:
        raise Exception(f'Failed to extract text from {filename}: {e}')
    
    return sanitize_content(content)

@app.route('/upload-context', methods=['POST'])
@limiter.limit("10 per minute")
@require_conversation_access
def upload_context():
    conversation_id = request.form.get('conversation_id')
    task_type = request.form.get('task_type', 'instructions')  # New: instructions, summary, analysis, etc.
    
    # Upload logging removed for security
    
    if not conversation_id:
        return jsonify({'error': 'Missing conversation_id'}), 400
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        return jsonify({'error': 'Invalid conversation ID'}), 400
    
    conversation = Conversation.query.get_or_404(conv_uuid)
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    
    # Validate file
    if not file.filename:
        return jsonify({'error': 'Empty filename not allowed'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    if not validate_file_size(file):
        return jsonify({'error': f'File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB'}), 400
    
    filename = sanitize_filename(secure_filename(file.filename))
    
    try:
        # Use generic content extractor
        content = extract_document_content(file, filename)
        
        # Apply task-specific processing
        processed_content = process_document_by_task(content, filename, task_type)
        
        # SIMPLIFIED UPLOAD: Clean, simple approach that just works
        app.logger.info(f"Processing upload for {filename}")
        
        try:
            import json
            
            # Get current documents
            docs = []
            if conversation.context_documents:
                if isinstance(conversation.context_documents, str):
                    docs = json.loads(conversation.context_documents)
                elif isinstance(conversation.context_documents, list):
                    docs = list(conversation.context_documents)
            
            # Add new document
            docs.append({
                'filename': filename, 
                'content': processed_content,
                'task_type': task_type,
                'original_content': content
            })
            
            # Update conversation
            conversation.context_documents = docs
            conversation.updated_at = datetime.utcnow()
            
            # Commit changes
            db.session.commit()
            
            app.logger.info(f"Successfully uploaded {filename}")
            
        except Exception as upload_error:
            app.logger.error(f"Upload failed: {str(upload_error)}")
            db.session.rollback()
            return jsonify({'error': f'Upload failed: {str(upload_error)}'}), 500
        
        # Get file type for icon
        file_type = get_file_type(filename)
        word_count = len(content.split()) if content else 0
        
        # Upload metadata logging removed for security
        
        preview = processed_content[:500] + ('...' if len(processed_content) > 500 else '')
        response_data = {
            'success': True, 
            'filename': filename, 
            'preview': preview,
            'task_type': task_type,
            'file_type': file_type,
            'file_size': len(content),
            'word_count': word_count
        }
        
        # Response logging removed for security
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Context extraction error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def get_file_type(filename):
    """Get file type for icon display"""
    ext = filename.rsplit('.', 1)[-1].lower()
    
    file_types = {
        'pdf': 'pdf',
        'doc': 'word', 'docx': 'word',
        'txt': 'text', 'md': 'text', 'csv': 'text',
        'jpg': 'image', 'jpeg': 'image', 'png': 'image', 'gif': 'image',
        'mp3': 'audio', 'wav': 'audio', 'm4a': 'audio',
        'mp4': 'video', 'avi': 'video', 'mov': 'video'
    }
    
    return file_types.get(ext, 'file')

def process_document_by_task(content, filename, task_type):
    """Process document content based on intended task"""
    
    task_prompts = {
        'instructions': f"Use this document as guidelines and instructions for your responses:\n\n{content}",
        'summary': f"Please summarize the following document ({filename}):\n\n{content}",
        'analysis': f"Please analyze the following document ({filename}):\n\n{content}",
        'reference': f"Reference document ({filename}) - use this information to answer questions:\n\n{content}",
        'template': f"Use this document as a template or example ({filename}):\n\n{content}"
    }
    
    return task_prompts.get(task_type, f"Document ({filename}):\n\n{content}")

@app.route('/extract-url', methods=['POST'])
@limiter.limit("5 per minute")
def extract_url_content():
    """Extract content from a URL and add it as context"""
    data = request.get_json()
    
    if not data or not data.get('url') or not data.get('conversation_id'):
        return jsonify({'error': 'URL and conversation_id are required'}), 400
    
    url = data['url']
    conversation_id = data['conversation_id']
    task_type = data.get('task_type', 'reference')
    
    try:
        conv_uuid = uuid.UUID(conversation_id)
        conversation = Conversation.query.get_or_404(conv_uuid)
        
        # Extract content from URL using requests and basic HTML parsing
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Try with different approaches if first fails
        session = requests.Session()
        session.headers.update(headers)
        
        try:
            response = session.get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
        except requests.exceptions.SSLError:
            # Try without SSL verification as fallback
            response = session.get(url, timeout=15, allow_redirects=True, verify=False)
            response.raise_for_status()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            # Try with HTTP instead of HTTPS
            if url.startswith('https://'):
                http_url = url.replace('https://', 'http://', 1)
                response = session.get(http_url, timeout=15, allow_redirects=True)
                response.raise_for_status()
            else:
                raise
        
        # Check content size
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB limit
            return jsonify({'error': 'URL content too large (max 10MB)'}), 400
        
        # Parse HTML and extract text
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text content
        content = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in content.splitlines())
        content = '\n'.join(line for line in lines if line)
        
        # Sanitize the extracted content
        content = sanitize_content(content)
        
        if not content:
            return jsonify({'error': 'No readable content found at URL'}), 400
        
        # Process content like uploaded documents
        processed_content = process_document_by_task(content, url, task_type)
        
        # Add to conversation context
        import json
        docs = conversation.context_documents
        if not docs:
            docs = []
        elif isinstance(docs, str):
            try:
                docs = json.loads(docs)
            except Exception:
                docs = []
        if not isinstance(docs, list):
            docs = []
        
        docs.append({
            'filename': url,
            'content': processed_content,
            'task_type': task_type,
            'original_content': content,
            'source_type': 'url'
        })
        
        conversation.context_documents = docs
        db.session.commit()
        
        # Extract title for display
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else url
        
        word_count = len(content.split()) if content else 0
        preview = content[:500] + ('...' if len(content) > 500 else '')
        
        return jsonify({
            'success': True,
            'url': url,
            'title': title,
            'preview': preview,
            'word_count': word_count,
            'task_type': task_type
        })
        
    except requests.RequestException as e:
        status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        error_str = str(e).lower()
        
        if status_code == 403:
            return jsonify({'error': 'Website blocked access. Try copying and pasting the content instead, or use a different URL.'}), 400
        elif status_code == 404:
            return jsonify({'error': 'URL not found (404). Please check the URL is correct.'}), 400
        elif status_code == 429:
            return jsonify({'error': 'Website rate limited our request. Please try again later.'}), 400
        elif 'connection aborted' in error_str or 'remote end closed' in error_str:
            return jsonify({'error': 'Website closed connection. The site may be down or blocking automated access. Try copying the content manually.'}), 400
        elif 'timeout' in error_str:
            return jsonify({'error': 'Website took too long to respond. Please try again or use a different URL.'}), 400
        elif 'ssl' in error_str:
            return jsonify({'error': 'SSL certificate issue. The website may have security problems.'}), 400
        else:
            return jsonify({'error': f'Failed to fetch URL: {str(e)}'}), 400
    except Exception as e:
        app.logger.error(f"URL extraction error: {e}", exc_info=True)
        return jsonify({'error': f'Failed to process URL: {str(e)}'}), 500

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # Prevent path traversal attacks
    filename = sanitize_filename(filename)
    
    # Additional security check - ensure file exists and is within upload folder
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    
    # Resolve any symbolic links and ensure path is within upload folder
    try:
        real_upload_folder = os.path.realpath(UPLOAD_FOLDER)
        real_file_path = os.path.realpath(file_path)
        
        # Check if the real file path starts with the real upload folder path
        if not real_file_path.startswith(real_upload_folder + os.sep) and real_file_path != real_upload_folder:
            app.logger.warning(f"Path traversal attempt blocked: {filename} -> {real_file_path}")
            return jsonify({'error': 'Access denied'}), 403
        
        # Check if file exists
        if not os.path.exists(real_file_path):
            return jsonify({'error': 'File not found'}), 404
            
    except Exception as e:
        app.logger.error(f"File access error: {e}")
        return jsonify({'error': 'File access error'}), 500
    
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/static/generated_images/<path:filename>')
def generated_image(filename):
    """Serve generated images from Stability AI"""
    # Prevent path traversal attacks
    filename = sanitize_filename(filename)
    
    images_dir = os.path.join(os.path.dirname(__file__), 'static', 'generated_images')
    file_path = os.path.join(images_dir, filename)
    
    # Security check - ensure path is within images directory
    try:
        real_images_dir = os.path.realpath(images_dir)
        real_file_path = os.path.realpath(file_path)
        
        if not real_file_path.startswith(real_images_dir + os.sep) and real_file_path != real_images_dir:
            app.logger.warning(f"Path traversal attempt blocked in images: {filename} -> {real_file_path}")
            return jsonify({'error': 'Access denied'}), 403
        
        if not os.path.exists(real_file_path):
            return jsonify({'error': 'Image not found'}), 404
            
    except Exception as e:
        app.logger.error(f"Generated image access error: {e}")
        return jsonify({'error': 'Image access error'}), 500
    
    return send_from_directory(images_dir, filename)

@app.route('/stability-edit-image', methods=['POST'])
@limiter.limit("10 per minute")
@auth.access_required(allow_free=True)
def stability_edit_image():
    """Handle Stability AI image editing requests"""
    try:
        # Get form data
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        image_file = request.files['image']
        prompt = request.form.get('prompt', '')
        model = request.form.get('model', 'stable-image-ultra')
        conversation_id = request.form.get('conversation_id')
        
        if not prompt:
            return jsonify({'error': 'Editing prompt is required'}), 400
        
        app.logger.info(f"Stability image edit request: model={model}, prompt_length={len(prompt)}")
        
        # Use the LLM service to edit the image
        from llm_service import LLMService
        llm_service = LLMService()
        
        # Process the image editing request
        response_message, tokens, cost = llm_service.edit_image(image_file, model, prompt)
        
        # Log usage for analytics
        try:
            from models import LLMUsageLog
            usage_log = LLMUsageLog(
                model=model,
                tokens=tokens,
                estimated_cost=cost,
                timestamp=datetime.utcnow()
            )
            db.session.add(usage_log)
            db.session.commit()
        except Exception as log_error:
            app.logger.warning(f"Failed to log usage: {log_error}")
        
        return jsonify({
            'response': response_message,
            'model': model,
            'timestamp': datetime.utcnow().isoformat(),
            'editing_request': True,
            'tokens': tokens,
            'cost': cost
        })
        
    except Exception as e:
        app.logger.error(f"Stability image editing error: {str(e)}", exc_info=True)
        return jsonify({'error': f'Image editing failed: {str(e)}'}), 500

@app.route('/llm-usage-stats', methods=['GET'])
def llm_usage_stats():
    from models import LLMUsageLog
    from sqlalchemy import func, cast, Date
    import datetime
    # Aggregate by model (existing)
    stats = db.session.query(
        LLMUsageLog.model,
        func.count().label('calls'),
        func.coalesce(func.sum(LLMUsageLog.tokens), 0).label('total_tokens'),
        func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0.0).label('total_cost')
    ).group_by(LLMUsageLog.model).all()
    result = [
        {
            'model': row.model,
            'calls': row.calls,
            'total_tokens': row.total_tokens,
            'total_cost': float(row.total_cost)
        }
        for row in stats
    ]
    # Aggregate by day and model for the last 14 days
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=13)
    timeseries = db.session.query(
        cast(LLMUsageLog.timestamp, Date).label('date'),
        LLMUsageLog.model,
        func.count().label('calls'),
        func.coalesce(func.sum(LLMUsageLog.tokens), 0).label('tokens'),
        func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0.0).label('cost')
    ).filter(LLMUsageLog.timestamp >= start_date).group_by('date', LLMUsageLog.model).order_by('date').all()
    timeseries_result = [
        {
            'date': row.date.isoformat(),
            'model': row.model,
            'calls': row.calls,
            'tokens': row.tokens,
            'cost': float(row.cost)
        }
        for row in timeseries
    ]
    return jsonify({'stats': result, 'timeseries': timeseries_result})

@app.route('/monthly-token-usage', methods=['GET'])
def monthly_token_usage():
    from models import LLMUsageLog
    from sqlalchemy import func, extract
    import datetime
    
    # Get token usage by model for each month in the last 12 months
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=365)
    
    monthly_stats = db.session.query(
        extract('year', LLMUsageLog.timestamp).label('year'),
        extract('month', LLMUsageLog.timestamp).label('month'),
        LLMUsageLog.model,
        func.coalesce(func.sum(LLMUsageLog.tokens), 0).label('total_tokens')
    ).filter(
        LLMUsageLog.timestamp >= start_date
    ).group_by(
        extract('year', LLMUsageLog.timestamp),
        extract('month', LLMUsageLog.timestamp),
        LLMUsageLog.model
    ).order_by('year', 'month').all()
    
    result = []
    for row in monthly_stats:
        month_name = datetime.date(int(row.year), int(row.month), 1).strftime('%Y-%m')
        result.append({
            'month': month_name,
            'model': row.model,
            'total_tokens': int(row.total_tokens)
        })
    
    return jsonify({'monthly_stats': result})

@app.route('/session-token-usage', methods=['GET'])
def session_token_usage():
    from models import LLMUsageLog
    from sqlalchemy import func
    import datetime
    
    # Get current session ID from cookie or generate one
    user_identity = get_user_identity()
    session_id = user_identity.get('session_id')
    user_id = user_identity.get('user_id')
    
    # For current session, we'll look at today's usage for the current user
    today = datetime.date.today()
    today_start = datetime.datetime.combine(today, datetime.time.min)
    
    query_filter = LLMUsageLog.timestamp >= today_start
    
    # Apply user-specific filter
    if user_id:
        # For authenticated users, filter by user_id (we need to add this to LLMUsageLog if not present)
        # For now, we'll show all usage for today as a placeholder
        pass
    elif session_id:
        # For free users, we'll show today's usage (could be enhanced with session tracking)
        pass
    
    session_stats = db.session.query(
        LLMUsageLog.model,
        func.coalesce(func.sum(LLMUsageLog.tokens), 0).label('total_tokens'),
        func.count().label('calls')
    ).filter(query_filter).group_by(LLMUsageLog.model).all()
    
    result = []
    for row in session_stats:
        result.append({
            'model': row.model,
            'total_tokens': int(row.total_tokens),
            'calls': int(row.calls)
        })
    
    return jsonify({'session_stats': result})

@app.route('/llm-error-log', methods=['GET'])
def llm_error_log():
    from models import LLMErrorLog
    errors = LLMErrorLog.query.order_by(LLMErrorLog.timestamp.desc()).limit(20).all()
    result = [
        {
            'timestamp': e.timestamp.isoformat(),
            'model': e.model,
            'error_message': e.error_message,
            'conversation_id': str(e.conversation_id) if e.conversation_id else None
        }
        for e in errors
    ]
    return jsonify({'errors': result})

@app.route('/api/log-error', methods=['POST'])
def log_client_error():
    """Log client-side JavaScript errors"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Log the client error
        app.logger.error(
            f"Client Error: {data.get('type', 'Unknown')} - {data.get('message', 'No message')} "
            f"URL: {data.get('url', 'Unknown')} "
            f"User-Agent: {data.get('userAgent', 'Unknown')}"
        )
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        app.logger.error(f"Failed to log client error: {e}")
        return jsonify({'error': 'Failed to log error'}), 500

# Admin IP Management Endpoints
@app.route('/admin/whitelist', methods=['GET'])
@auth.login_required
def get_ip_whitelist():
    """Get all whitelisted IPs"""
    from models import IPWhitelist
    whitelist = IPWhitelist.query.filter_by(is_active=True).order_by(IPWhitelist.created_at.desc()).all()
    
    return jsonify([
        {
            'id': str(entry.id),
            'ip_address': entry.ip_address,
            'description': entry.description,
            'created_at': entry.created_at.isoformat(),
            'created_by': entry.created_by
        }
        for entry in whitelist
    ])

@app.route('/admin/whitelist', methods=['POST'])
@auth.login_required
def add_ip_to_whitelist():
    """Add IP to whitelist"""
    from auth import FreeAccessManager
    
    data = request.get_json()
    if not data or not data.get('ip_address'):
        return jsonify({'error': 'IP address is required'}), 400
    
    ip_address = data['ip_address'].strip()
    description = data.get('description', 'Demo Access')
    created_by = data.get('created_by', 'admin')
    
    success, message = FreeAccessManager.add_to_whitelist(ip_address, description, created_by)
    
    if success:
        return jsonify({'message': message}), 201
    else:
        return jsonify({'error': message}), 400

@app.route('/admin/whitelist/<ip_address>', methods=['DELETE'])
@auth.login_required  
def remove_ip_from_whitelist(ip_address):
    """Remove IP from whitelist"""
    from auth import FreeAccessManager
    
    success, message = FreeAccessManager.remove_from_whitelist(ip_address)
    
    if success:
        return jsonify({'message': message})
    else:
        return jsonify({'error': message}), 404

@app.route('/admin/usage-stats', methods=['GET'])
@auth.login_required
def get_usage_stats():
    """Get comprehensive usage statistics"""
    from models import IPUsageSummary, FreeAccessLog, IPWhitelist
    from sqlalchemy import func, desc
    from datetime import datetime, timedelta
    
    # Get top IPs by usage in last 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    top_ips = db.session.query(
        FreeAccessLog.ip_address,
        func.count(FreeAccessLog.id).label('total_queries'),
        func.count(func.distinct(FreeAccessLog.session_id)).label('unique_sessions'),
        func.max(FreeAccessLog.timestamp).label('last_activity')
    ).filter(
        FreeAccessLog.timestamp >= week_ago
    ).group_by(
        FreeAccessLog.ip_address
    ).order_by(
        desc('total_queries')
    ).limit(20).all()
    
    # Get whitelist count
    whitelist_count = IPWhitelist.query.filter_by(is_active=True).count()
    
    # Get today's stats
    today = datetime.utcnow().date()
    today_stats = db.session.query(
        func.sum(IPUsageSummary.total_queries).label('total_queries'),
        func.count(func.distinct(IPUsageSummary.ip_address)).label('unique_ips')
    ).filter(IPUsageSummary.date == today).first()
    
    return jsonify({
        'top_ips': [
            {
                'ip_address': row.ip_address,
                'total_queries': row.total_queries,
                'unique_sessions': row.unique_sessions,
                'last_activity': row.last_activity.isoformat() if row.last_activity else None
            }
            for row in top_ips
        ],
        'whitelist_count': whitelist_count,
        'today_stats': {
            'total_queries': today_stats.total_queries or 0,
            'unique_ips': today_stats.unique_ips or 0
        }
    })

@app.route('/admin/current-ip', methods=['GET'])
def get_current_ip():
    """Get current user's IP for easy whitelisting"""
    from auth import FreeAccessManager
    
    ip = FreeAccessManager.get_client_ip()
    is_whitelisted, whitelist_entry = FreeAccessManager.is_whitelisted(ip)
    
    return jsonify({
        'ip_address': ip,
        'is_whitelisted': is_whitelisted,
        'whitelist_info': {
            'description': whitelist_entry.description if whitelist_entry else None,
            'created_at': whitelist_entry.created_at.isoformat() if whitelist_entry else None
        } if whitelist_entry else None
    })

# ==================== PERSONA MANAGEMENT API ENDPOINTS ====================

@app.route('/api/personas', methods=['GET'])
def get_personas():
    """Get all personas"""
    try:
        personas = Persona.query.filter_by(is_active=True).order_by(Persona.category, Persona.name).all()
        return jsonify({
            'success': True,
            'personas': [persona.to_dict() for persona in personas]
        })
    except Exception as e:
        app.logger.error(f"Error fetching personas: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch personas'}), 500

@app.route('/api/personas', methods=['POST'])
def create_persona():
    """Create a new persona"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'agent_name', 'role', 'traits', 'category']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        # Get current user
        identity = get_user_identity()
        created_by = identity.get('user_id') or 'admin'
        
        persona = Persona(
            name=data['name'],
            agent_name=data['agent_name'],
            role=data['role'],
            traits=data['traits'],
            category=data['category'],
            description=data.get('description', ''),
            created_by=created_by
        )
        
        db.session.add(persona)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'persona': persona.to_dict()
        })
    except Exception as e:
        app.logger.error(f"Error creating persona: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to create persona'}), 500

@app.route('/api/personas/<persona_id>', methods=['GET'])
def get_persona(persona_id):
    """Get a single persona by ID"""
    try:
        persona = Persona.query.get_or_404(persona_id)
        return jsonify({
            'success': True,
            'persona': persona.to_dict()
        })
    except Exception as e:
        app.logger.error(f"Error fetching persona {persona_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch persona'}), 500

@app.route('/api/personas/<persona_id>', methods=['PUT'])
def update_persona(persona_id):
    """Update a persona"""
    try:
        persona = Persona.query.get_or_404(persona_id)
        data = request.get_json()
        
        # Update fields
        if 'name' in data:
            persona.name = data['name']
        if 'agent_name' in data:
            persona.agent_name = data['agent_name']
        if 'role' in data:
            persona.role = data['role']
        if 'traits' in data:
            persona.traits = data['traits']
        if 'category' in data:
            persona.category = data['category']
        if 'description' in data:
            persona.description = data['description']
        if 'is_active' in data:
            persona.is_active = data['is_active']
        
        persona.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'persona': persona.to_dict()
        })
    except Exception as e:
        app.logger.error(f"Error updating persona: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to update persona'}), 500

@app.route('/api/personas/<persona_id>', methods=['DELETE'])
def delete_persona(persona_id):
    """Delete a persona"""
    try:
        persona = Persona.query.get_or_404(persona_id)
        
        # Check if persona is being used by any projects
        projects_using_persona = Project.query.filter_by(persona_id=persona.id).count()
        if projects_using_persona > 0:
            return jsonify({
                'success': False, 
                'error': f'Cannot delete persona. It is being used by {projects_using_persona} project(s).'
            }), 400
        
        db.session.delete(persona)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error deleting persona: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to delete persona'}), 500

@app.route('/api/personas/categories', methods=['GET'])
def get_persona_categories():
    """Get all persona categories"""
    try:
        categories = db.session.query(Persona.category).filter_by(is_active=True).distinct().all()
        return jsonify({
            'success': True,
            'categories': [cat[0] for cat in categories]
        })
    except Exception as e:
        app.logger.error(f"Error fetching persona categories: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch categories'}), 500

# ==================== END PERSONA MANAGEMENT API ====================

# ==================== CONTEXT MANAGEMENT API ENDPOINTS ====================

@app.route('/api/context', methods=['GET'])
def get_context_items():
    """Get all context items for current user"""
    try:
        app.logger.info("🔍 API: Getting context items")
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        items = ContextService.get_user_context_items(include_inactive=include_inactive)
        
        app.logger.info(f"📋 Found {len(items)} context items")
        
        return jsonify({
            'success': True,
            'items': [
                {
                    'id': str(item.id),
                    'name': item.name,
                    'description': item.description,
                    'content_type': item.content_type,
                    'token_count': item.token_count,
                    'usage_count': item.usage_count,
                    'created_at': item.created_at.isoformat(),
                    'last_used_at': item.last_used_at.isoformat() if item.last_used_at else None,
                    'is_active': item.is_active,
                    'file_size': item.file_size,
                    'original_filename': item.original_filename,
                    'project_id': str(item.project_id) if item.project_id else None,
                    'project_name': item.project.name if item.project else None
                }
                for item in items
            ]
        })
    except Exception as e:
        app.logger.error(f"❌ Error fetching context items: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to fetch context items'}), 500

@app.route('/api/context', methods=['POST'])
def create_context_item():
    """Create a new context item"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or not data.get('name') or not data.get('content_type'):
            return jsonify({'success': False, 'error': 'Name and content_type are required'}), 400
        
        # Create context item
        context_item = ContextService.create_context_item(
            name=data['name'],
            content_type=data['content_type'],
            content_text=data.get('content_text'),
            description=data.get('description'),
            original_filename=data.get('original_filename'),
            file_path=data.get('file_path'),
            file_size=data.get('file_size'),
            extra_data=data.get('extra_data')
        )
        
        return jsonify({
            'success': True,
            'item': {
                'id': str(context_item.id),
                'name': context_item.name,
                'description': context_item.description,
                'content_type': context_item.content_type,
                'token_count': context_item.token_count,
                'created_at': context_item.created_at.isoformat()
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error creating context item: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to create context item'}), 500

@app.route('/api/context/<item_id>', methods=['GET'])
def get_context_item(item_id):
    """Get specific context item by ID"""
    try:
        item = ContextService.get_context_item(item_id)
        if not item:
            return jsonify({'success': False, 'error': 'Context item not found'}), 404
        
        return jsonify({
            'success': True,
            'item': {
                'id': str(item.id),
                'name': item.name,
                'description': item.description,
                'content_type': item.content_type,
                'content_text': item.content_text,
                'content_summary': item.content_summary,
                'token_count': item.token_count,
                'usage_count': item.usage_count,
                'created_at': item.created_at.isoformat(),
                'updated_at': item.updated_at.isoformat(),
                'last_used_at': item.last_used_at.isoformat() if item.last_used_at else None,
                'is_active': item.is_active,
                'original_filename': item.original_filename,
                'file_path': item.file_path,
                'file_size': item.file_size,
                'extra_data': item.extra_data
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error fetching context item {item_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch context item'}), 500

@app.route('/api/context/<item_id>', methods=['PUT'])
def update_context_item(item_id):
    """Update existing context item"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        updated_item = ContextService.update_context_item(
            item_id=item_id,
            name=data.get('name'),
            description=data.get('description'),
            content_type=data.get('content_type'),
            content_text=data.get('content_text'),
            project_id=data.get('project_id'),
            extra_data=data.get('extra_data')
        )
        
        if not updated_item:
            return jsonify({'success': False, 'error': 'Context item not found'}), 404
        
        return jsonify({
            'success': True,
            'item': {
                'id': str(updated_item.id),
                'name': updated_item.name,
                'description': updated_item.description,
                'content_type': updated_item.content_type,
                'token_count': updated_item.token_count,
                'updated_at': updated_item.updated_at.isoformat()
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error updating context item {item_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to update context item'}), 500

@app.route('/api/context/<item_id>', methods=['DELETE'])
def delete_context_item(item_id):
    """Soft delete context item"""
    try:
        success = ContextService.delete_context_item(item_id)
        if not success:
            return jsonify({'success': False, 'error': 'Context item not found'}), 404
        
        return jsonify({'success': True, 'message': 'Context item deleted'})
    
    except Exception as e:
        app.logger.error(f"Error deleting context item {item_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to delete context item'}), 500

@app.route('/api/context/suggestions', methods=['GET'])
def get_context_suggestions():
    """Get context suggestions based on query text"""
    try:
        query_text = request.args.get('query', '')
        conversation_id = request.args.get('conversation_id')
        limit = int(request.args.get('limit', 5))
        
        if not query_text:
            return jsonify({'success': False, 'error': 'Query text is required'}), 400
        
        suggestions = ContextService.get_context_suggestions(
            query_text=query_text,
            conversation_id=conversation_id,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
    
    except Exception as e:
        app.logger.error(f"Error getting context suggestions: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get suggestions'}), 500

@app.route('/api/conversation/<conversation_id>/context', methods=['GET'])
def get_conversation_context(conversation_id):
    """Get all active context for a conversation"""
    try:
        app.logger.info(f"💬 API: Getting conversation context for {conversation_id}")
        
        # Get new context items from ContextService
        context = ContextService.get_conversation_context(conversation_id)
        app.logger.info(f"💬 ContextService returned {len(context)} items")
        
        # Also get legacy context_documents from conversation
        conversation = Conversation.query.get_or_404(conversation_id)
        legacy_docs = []
        
        if conversation.context_documents:
            import json
            docs = conversation.context_documents
            if isinstance(docs, str):
                docs = json.loads(docs)
            
            app.logger.info(f"💬 Found {len(docs)} legacy documents")
            
            for i, doc in enumerate(docs):
                legacy_docs.append({
                    'session_id': f'legacy_{i}',
                    'item_id': f'legacy_{i}',
                    'name': doc.get('filename', 'Unknown'),
                    'description': f"Legacy document - {doc.get('task_type', 'instructions')}",
                    'content_type': 'document',
                    'content_text': doc.get('content', ''),
                    'content_summary': doc.get('content', '')[:200] + '...' if len(doc.get('content', '')) > 200 else doc.get('content', ''),
                    'token_count': len(doc.get('content', '').split()) if doc.get('content') else 0,
                    'relevance_score': 1.0,
                    'added_at': conversation.updated_at.isoformat() if conversation.updated_at else conversation.created_at.isoformat(),
                    'last_accessed_at': conversation.updated_at.isoformat() if conversation.updated_at else conversation.created_at.isoformat(),
                    'is_legacy': True
                })
        else:
            app.logger.info("💬 No legacy documents found")
        
        # Combine both sources
        all_context = context + legacy_docs
        app.logger.info(f"💬 Returning {len(all_context)} total context items")
        
        return jsonify({
            'success': True,
            'context': all_context
        })
    
    except Exception as e:
        app.logger.error(f"❌ Error fetching conversation context: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to fetch conversation context'}), 500

@app.route('/api/conversation/<conversation_id>/context/<context_item_id>', methods=['POST'])
def add_context_to_conversation(conversation_id, context_item_id):
    """Add context item to conversation"""
    try:
        data = request.get_json() or {}
        relevance_score = float(data.get('relevance_score', 1.0))
        
        context_session = ContextService.add_context_to_conversation(
            conversation_id=conversation_id,
            context_item_id=context_item_id,
            relevance_score=relevance_score
        )
        
        if not context_session:
            return jsonify({'success': False, 'error': 'Context item not found or access denied'}), 404
        
        return jsonify({
            'success': True,
            'session': {
                'id': str(context_session.id),
                'conversation_id': str(context_session.conversation_id),
                'context_item_id': str(context_session.context_item_id),
                'relevance_score': float(context_session.relevance_score),
                'added_at': context_session.added_at.isoformat(),
                'is_active': context_session.is_active
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error adding context to conversation: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to add context to conversation'}), 500

@app.route('/api/conversation/<conversation_id>/context/<context_item_id>', methods=['DELETE'])
def remove_context_from_conversation(conversation_id, context_item_id):
    """Remove context item from conversation"""
    try:
        success = ContextService.remove_context_from_conversation(
            conversation_id=conversation_id,
            context_item_id=context_item_id
        )
        
        if not success:
            return jsonify({'success': False, 'error': 'Context not found in conversation'}), 404
        
        return jsonify({'success': True, 'message': 'Context removed from conversation'})
    
    except Exception as e:
        app.logger.error(f"Error removing context from conversation: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to remove context from conversation'}), 500

@app.route('/api/context/stats', methods=['GET'])
def get_context_stats():
    """Get user context statistics"""
    try:
        app.logger.info("📊 API: Getting context stats")
        conversation_id = request.args.get('conversation_id')
        app.logger.info(f"📊 Conversation ID: {conversation_id}")
        
        stats = ContextService.get_user_stats()
        app.logger.info(f"📊 Base stats: {stats}")
        
        # Add legacy document stats from current conversation
        if conversation_id:
            try:
                conversation = Conversation.query.get(conversation_id)
                if conversation and conversation.context_documents:
                    import json
                    docs = conversation.context_documents
                    if isinstance(docs, str):
                        docs = json.loads(docs)
                    
                    legacy_count = len(docs)
                    legacy_tokens = sum(len(doc.get('content', '').split()) for doc in docs)
                    
                    stats['total_items'] += legacy_count
                    stats['total_tokens'] += legacy_tokens
                    stats['legacy_items'] = legacy_count
                    stats['legacy_tokens'] = legacy_tokens
                    
                    app.logger.info(f"📊 Added legacy stats: {legacy_count} items, {legacy_tokens} tokens")
            except Exception as e:
                app.logger.warning(f"⚠️ Could not add legacy stats: {e}")
        
        app.logger.info(f"📊 Final stats: {stats}")
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        app.logger.error(f"❌ Error fetching context stats: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to fetch context stats'}), 500

# ==================== END CONTEXT MANAGEMENT API ====================

# ==================== SEARCH API ENDPOINTS ====================

@app.route('/api/search/conversations', methods=['GET'])
def search_conversations():
    """Search conversations by content with project awareness"""
    try:
        query = request.args.get('query', '').strip()
        project_id = request.args.get('project_id')
        limit = int(request.args.get('limit', 20))
        
        if not query:
            return jsonify({'success': False, 'error': 'Query parameter is required'}), 400
        
        from sqlalchemy import or_, and_, exists
        from models import Conversation, Message
        
        # Build search filter using EXISTS for better performance and no DISTINCT issues
        message_exists = exists().where(
            and_(
                Message.conversation_id == Conversation.id,
                Message.content.ilike(f'%{query}%')
            )
        )
        
        # For now, let's skip tag search in the backend to avoid SQL compatibility issues
        # The frontend already does client-side tag filtering for short queries
        search_filter = or_(
            Conversation.title.ilike(f'%{query}%'),
            message_exists
        )
        
        # Build base query with user filtering and search filter
        base_query = filter_conversations_by_user(db.session.query(Conversation)).filter(search_filter)
        
        if project_id:
            try:
                project_uuid = uuid.UUID(project_id)
                base_query = base_query.filter(Conversation.project_id == project_uuid)
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid project_id'}), 400
        
        # Get conversations ordered by most recent (no DISTINCT needed with EXISTS)
        conversations = base_query.order_by(Conversation.updated_at.desc()).limit(limit).all()
        
        # Format results with matching message snippets
        results = []
        for conv in conversations:
            # Find matching messages in this conversation
            matching_messages = Message.query.filter(
                and_(
                    Message.conversation_id == conv.id,
                    Message.content.ilike(f'%{query}%')
                )
            ).order_by(Message.timestamp.desc()).limit(3).all()
            
            # Create snippets from matching messages
            snippets = []
            for msg in matching_messages:
                content = msg.content
                # Find the query in content and create a snippet around it
                query_lower = query.lower()
                content_lower = content.lower()
                
                if query_lower in content_lower:
                    start_idx = content_lower.find(query_lower)
                    snippet_start = max(0, start_idx - 50)
                    snippet_end = min(len(content), start_idx + len(query) + 50)
                    snippet = content[snippet_start:snippet_end]
                    
                    if snippet_start > 0:
                        snippet = "..." + snippet
                    if snippet_end < len(content):
                        snippet = snippet + "..."
                    
                    snippets.append({
                        'content': snippet,
                        'role': msg.role,
                        'timestamp': msg.timestamp.isoformat()
                    })
            
            # If no message matches but title matches, use title
            if not snippets and query.lower() in conv.title.lower():
                snippets.append({
                    'content': conv.title,
                    'role': 'title',
                    'timestamp': conv.created_at.isoformat()
                })
            
            results.append({
                'id': str(conv.id),
                'title': conv.title,
                'project_id': str(conv.project_id) if conv.project_id else None,
                'created_at': conv.created_at.isoformat(),
                'updated_at': conv.updated_at.isoformat(),
                'tags': conv.tags or [],
                'snippets': snippets[:2]  # Limit to 2 snippets per conversation
            })
        
        return jsonify({
            'success': True,
            'query': query,
            'project_id': project_id,
            'total_results': len(results),
            'conversations': results
        })
        
    except Exception as e:
        app.logger.error(f"Error searching conversations: {str(e)}")
        return jsonify({'success': False, 'error': 'Search failed'}), 500

@app.route('/api/search/projects', methods=['GET'])
def search_projects():
    """Search projects by name"""
    try:
        query = request.args.get('query', '').strip()
        limit = int(request.args.get('limit', 20))
        
        if not query:
            return jsonify({'success': False, 'error': 'Query parameter is required'}), 400
        
        from models import Project
        
        # For now, search all projects (no user filtering implemented yet)
        # TODO: Implement proper user filtering for projects
        projects = db.session.query(Project).filter(
            Project.name.ilike(f'%{query}%')
        ).order_by(Project.created_at.desc()).limit(limit).all()
        
        # Format results
        results = []
        for proj in projects:
            # Count conversations in this project
            conversation_count = db.session.query(Conversation).filter(
                Conversation.project_id == proj.id
            ).count()
            
            results.append({
                'id': str(proj.id),
                'name': proj.name,
                'description': proj.description,
                'created_at': proj.created_at.isoformat(),
                'updated_at': proj.updated_at.isoformat(),
                'conversation_count': conversation_count
            })
        
        return jsonify({
            'success': True,
            'query': query,
            'total_results': len(results),
            'projects': results
        })
        
    except Exception as e:
        app.logger.error(f"Error searching projects: {str(e)}")
        return jsonify({'success': False, 'error': 'Search failed'}), 500

@app.route('/api/search/context', methods=['GET'])
def search_context():
    """Search context items by filename and content"""
    try:
        query = request.args.get('query', '').strip()
        limit = int(request.args.get('limit', 20))
        
        if not query:
            return jsonify({'success': False, 'error': 'Query parameter is required'}), 400
        
        from models import ContextItem, Project
        from sqlalchemy import or_
        
        # Search context items by filename and content
        # For now, search all context items (no user filtering implemented yet)
        # TODO: Implement proper user filtering for context items
        context_items = db.session.query(ContextItem).filter(
            or_(
                ContextItem.filename.ilike(f'%{query}%'),
                ContextItem.content.ilike(f'%{query}%')
            )
        ).order_by(ContextItem.created_at.desc()).limit(limit).all()
        
        # Format results
        results = []
        for item in context_items:
            # Get project name if available
            project_name = None
            if item.project_id:
                project = db.session.get(Project, item.project_id)
                if project:
                    project_name = project.name
            
            # Create content preview
            content_preview = item.content[:200] + "..." if len(item.content) > 200 else item.content
            
            results.append({
                'id': str(item.id),
                'filename': item.filename,
                'content_type': item.content_type,
                'content_preview': content_preview,
                'conversation_id': str(item.conversation_id) if item.conversation_id else None,
                'project_id': str(item.project_id) if item.project_id else None,
                'project_name': project_name,
                'created_at': item.created_at.isoformat(),
                'updated_at': item.updated_at.isoformat()
            })
        
        return jsonify({
            'success': True,
            'query': query,
            'total_results': len(results),
            'context_items': results
        })
        
    except Exception as e:
        app.logger.error(f"Error searching context items: {str(e)}")
        return jsonify({'success': False, 'error': 'Search failed'}), 500

# ==================== END SEARCH API ====================

# ==================== TAG API ====================

@app.route('/api/conversations/<conversation_id>/tags', methods=['GET'])
def get_conversation_tags(conversation_id):
    """Get tags for a specific conversation"""
    try:
        conversation = db.session.get(Conversation, conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        return jsonify({
            'success': True,
            'conversation_id': conversation_id,
            'tags': conversation.tags or []
        })
    
    except Exception as e:
        app.logger.error(f"Error getting conversation tags: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get tags'}), 500

@app.route('/api/conversations/<conversation_id>/tags', methods=['POST'])
def add_conversation_tags(conversation_id):
    """Add tags to a conversation"""
    try:
        data = request.get_json()
        if not data or 'tags' not in data:
            return jsonify({'error': 'Tags are required'}), 400
        
        new_tags = data['tags']
        if not isinstance(new_tags, list):
            return jsonify({'error': 'Tags must be a list'}), 400
        
        # Clean and validate tags
        cleaned_tags = []
        for tag in new_tags:
            if isinstance(tag, str) and tag.strip():
                # Convert to lowercase and remove special characters for consistency
                clean_tag = ''.join(c for c in tag.strip() if c.isalnum() or c in '-_').lower()
                if clean_tag and len(clean_tag) <= 50:
                    cleaned_tags.append(clean_tag)
        
        if not cleaned_tags:
            return jsonify({'error': 'No valid tags provided'}), 400
        
        conversation = db.session.get(Conversation, conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Merge with existing tags
        existing_tags = conversation.tags or []
        all_tags = list(set(existing_tags + cleaned_tags))  # Remove duplicates
        
        conversation.tags = all_tags
        db.session.commit()
        
        return jsonify({
            'success': True,
            'conversation_id': conversation_id,
            'tags': all_tags,
            'added_tags': cleaned_tags
        })
    
    except Exception as e:
        app.logger.error(f"Error adding conversation tags: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to add tags'}), 500

@app.route('/api/conversations/<conversation_id>/tags', methods=['DELETE'])
def remove_conversation_tag(conversation_id):
    """Remove a single tag from a conversation"""
    try:
        data = request.get_json()
        if not data or 'tag' not in data:
            return jsonify({'error': 'Tag is required'}), 400
        
        tag_to_remove = data['tag'].strip().lower()
        
        conversation = db.session.get(Conversation, conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        existing_tags = conversation.tags or []
        if tag_to_remove in existing_tags:
            existing_tags.remove(tag_to_remove)
            conversation.tags = existing_tags
            db.session.commit()
        
        return jsonify({
            'success': True,
            'conversation_id': conversation_id,
            'tags': existing_tags,
            'removed_tag': tag_to_remove
        })
    
    except Exception as e:
        app.logger.error(f"Error removing conversation tag: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to remove tag'}), 500

@app.route('/api/tags', methods=['GET'])
def get_all_tags():
    """Get all unique tags from all conversations"""
    try:
        # Query all conversations and collect unique tags
        conversations = db.session.query(Conversation).filter(
            Conversation.tags.isnot(None)
        ).all()
        
        all_tags = set()
        for conv in conversations:
            if conv.tags and isinstance(conv.tags, list):
                all_tags.update(conv.tags)
        
        # Sort tags alphabetically
        sorted_tags = sorted(list(all_tags))
        
        return jsonify({
            'success': True,
            'tags': sorted_tags,
            'total_tags': len(sorted_tags)
        })
    
    except Exception as e:
        app.logger.error(f"Error getting all tags: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get tags'}), 500

# ==================== END TAG API ====================

# ==================== MODEL SETTINGS API ====================

@app.route('/api/model-settings', methods=['GET'])
def get_model_settings():
    """Get current model settings from database"""
    try:
        # Check if user is authenticated (but don't fail if auth is not available)
        user_id = None
        try:
            from auth import current_user_id
            user_id = current_user_id()
        except ImportError:
            # Auth module not available, continue without authentication
            pass
        
        # Load settings from database
        from models import ModelSettings
        
        try:
            # Get all model settings from database
            model_settings = ModelSettings.query.all()
            
            # Convert to dictionary format expected by frontend
            settings = {}
            for model_setting in model_settings:
                settings[model_setting.model_name] = {
                    'enabled': model_setting.enabled,
                    'status': model_setting.status
                }
            
            app.logger.info(f"Loaded {len(settings)} model settings from database")
            app.logger.info(f"Model settings retrieved for user {user_id}")
            return jsonify(settings)
            
        except Exception as e:
            app.logger.error(f"Failed to load model settings from database: {str(e)}")
            # Fallback to default settings if database fails
            settings = {
                'gpt-3.5-turbo': {'enabled': True, 'status': 'unknown'},
                'gpt-4': {'enabled': True, 'status': 'unknown'},
                'gpt-4-turbo': {'enabled': True, 'status': 'unknown'},
                'gpt-4o': {'enabled': True, 'status': 'unknown'},
                'gpt-4o-mini': {'enabled': True, 'status': 'unknown'},
                'gpt-5': {'enabled': False, 'status': 'unknown'},  # Disabled by default
                'o1-preview': {'enabled': True, 'status': 'unknown'},
                'o1-mini': {'enabled': True, 'status': 'unknown'},
                'claude-3.5-sonnet': {'enabled': True, 'status': 'unknown'},
                'claude-3-opus': {'enabled': True, 'status': 'unknown'},
                'claude-3-sonnet': {'enabled': True, 'status': 'unknown'},
                'claude-3-haiku': {'enabled': True, 'status': 'unknown'},
                'gemini-pro': {'enabled': True, 'status': 'unknown'},
                'gemini-flash': {'enabled': True, 'status': 'unknown'},
                'llama2-70b': {'enabled': True, 'status': 'unknown'},
                'mixtral-8x7b': {'enabled': True, 'status': 'unknown'},
                'codellama-34b': {'enabled': True, 'status': 'unknown'},
                'stable-image-ultra': {'enabled': True, 'status': 'unknown'},
                'stable-image-core': {'enabled': True, 'status': 'unknown'},
                'stable-image-sd3': {'enabled': True, 'status': 'unknown'},
                'stable-audio-2': {'enabled': True, 'status': 'unknown'}
            }
            app.logger.info(f"Using fallback default settings: {settings}")
        return jsonify(settings)
    
    except Exception as e:
        app.logger.error(f"Error getting model settings: {str(e)}")
        return jsonify({'error': 'Failed to get model settings'}), 500

@csrf.exempt
@app.route('/api/model-settings', methods=['POST'])
def save_model_settings():
    """Save model settings to database"""
    try:
        # Check if user is authenticated (but don't fail if auth is not available)
        user_id = None
        try:
            from auth import current_user_id
            user_id = current_user_id()
        except ImportError:
            # Auth module not available, continue without authentication
            pass
        
        settings = request.get_json()
        if not settings:
            return jsonify({'error': 'No settings provided'}), 400
        
        app.logger.info(f"Received settings: {settings}")
        
        # Remove csrf_token if present (it's not a model setting)
        if 'csrf_token' in settings:
            del settings['csrf_token']
        
        # Save settings to database
        from models import ModelSettings, db
        
        try:
            # Update or create each model setting
            for model_name, model_data in settings.items():
                model_setting = ModelSettings.query.filter_by(model_name=model_name).first()
                
                if model_setting:
                    # Update existing setting
                    model_setting.enabled = model_data.get('enabled', True)
                    model_setting.status = model_data.get('status', 'unknown')
                    model_setting.updated_at = datetime.utcnow()
                else:
                    # Create new setting
                    model_setting = ModelSettings(
                        model_name=model_name,
                        enabled=model_data.get('enabled', True),
                        status=model_data.get('status', 'unknown')
                    )
                    db.session.add(model_setting)
            
            # Commit all changes
            db.session.commit()
            app.logger.info(f"Model settings saved to database for user {user_id}")
            return jsonify({'success': True, 'message': 'Settings saved successfully'})
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Failed to save model settings to database: {str(e)}")
            
            # Fallback to file system if database fails
            app.logger.info("Falling back to file system storage")
            try:
                import json
                os.makedirs(app.instance_path, exist_ok=True)
                settings_file = os.path.join(app.instance_path, 'model_settings.json')
                with open(settings_file, 'w') as f:
                    json.dump(settings, f, indent=2)
                    app.logger.info(f"Model settings saved to file as fallback for user {user_id}")
                    return jsonify({'success': True, 'message': 'Settings saved successfully (file fallback)'})
            except Exception as file_error:
                app.logger.error(f"File fallback also failed: {str(file_error)}")
                return jsonify({'error': f'Failed to save model settings: Database error: {str(e)}, File error: {str(file_error)}'}), 500
    
    except Exception as e:
        app.logger.error(f"Error saving model settings: {str(e)}")
        return jsonify({'error': 'Failed to save model settings'}), 500

@csrf.exempt
@app.route('/api/check-model-access', methods=['POST'])
def check_model_access():
    """Check if a specific model is accessible by attempting a real API call"""
    try:
        app.logger.info("check_model_access endpoint called")
        
        data = request.get_json()
        if not data:
            app.logger.error("No JSON data received")
            return jsonify({'error': 'No data provided'}), 400
            
        model = data.get('model')
        if not model:
            app.logger.error("No model specified in request")
            return jsonify({'error': 'Model not specified'}), 400
        
        app.logger.info(f"Checking access for model: {model}")
        
        # Get model info from dynamic model list to find custom API key
        models_file = os.path.join(app.instance_path, 'available_models.json')
        provider = None
        custom_api_key = None
        
        if os.path.exists(models_file):
            import json
            with open(models_file, 'r') as f:
                models = json.load(f)
            
            # Find the model in our dynamic list
            for model_info in models:
                if model_info['name'] == model:
                    provider = model_info['provider']
                    custom_api_key = model_info.get('api_key')
                    break
        
        # Check if model is accessible by attempting a real test call
        has_access = False
        api_key_name = None
        error_details = None
        
        try:
            # Determine provider and API key from model name or custom config
            if custom_api_key:
                api_key_name = custom_api_key
                api_key_value = os.getenv(custom_api_key)
                app.logger.info(f"Checking custom API key {custom_api_key}: {'configured' if api_key_value and api_key_value.strip() else 'not configured'}")
            else:
                # Pattern matching for standard models
                if model.startswith('gpt-') or model.startswith('o1-'):
                    api_key_name = 'OPENAI_API_KEY'
                    api_key_value = os.getenv('OPENAI_API_KEY')
                elif model.startswith('claude-'):
                    api_key_name = 'CLAUDE_API_KEY'
                    api_key_value = os.getenv('CLAUDE_API_KEY')
                elif model.startswith('gemini-'):
                    api_key_name = 'GEMINI_API_KEY'
                    api_key_value = os.getenv('GEMINI_API_KEY')
                elif model in ['llama2-70b', 'mixtral-8x7b', 'mistral-7b', 'codellama-34b']:
                    api_key_name = 'HUGGING_FACE_API_KEY'
                    api_key_value = os.getenv('HUGGING_FACE_API_KEY')
                elif model.startswith('stable-'):
                    api_key_name = 'STABILITY_API_KEY'
                    api_key_value = os.getenv('STABILITY_API_KEY')
                else:
                    api_key_name = 'Unknown'
                    api_key_value = None
            
            # If no API key is configured, can't access
            if not api_key_value or not api_key_value.strip():
                error_details = f"API key {api_key_name} not configured"
                app.logger.info(f"Model {model}: {error_details}")
            else:
                # Perform actual API test call
                has_access, error_details = _test_model_api_call(model, api_key_name, api_key_value)
                
        except Exception as model_error:
            app.logger.error(f"Error checking model {model} access: {str(model_error)}")
            error_details = str(model_error)
            has_access = False
        
        app.logger.info(f"Model {model} access check result: {has_access} (API key: {api_key_name}, error: {error_details})")
        
        return jsonify({
            'success': True,
            'model': model,
            'provider': provider,
            'api_key_name': api_key_name,
            'hasAccess': has_access,
            'status': 'Available' if has_access else 'Not accessible',
            'error': error_details,
            'debugInfo': {
            'model': model,
            'provider': provider,
            'api_key_name': api_key_name,
                'tested': True
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error in check_model_access: {str(e)}")
        return jsonify({'error': f'Failed to check model access: {str(e)}'}), 500


def _test_model_api_call(model, api_key_name, api_key_value):
    """
    Perform an actual API call to test if model is accessible.
    Returns tuple: (has_access: bool, error_message: str or None)
    """
    try:
        if model.startswith('gpt-') or model.startswith('o1-'):
            return _test_openai_model(model, api_key_value)
        elif model.startswith('claude-'):
            return _test_anthropic_model(model, api_key_value)
        elif model.startswith('gemini-'):
            return _test_gemini_model(model, api_key_value)
        elif model in ['llama2-70b', 'mixtral-8x7b', 'mistral-7b', 'codellama-34b']:
            return _test_huggingface_model(model, api_key_value)
        elif model.startswith('stable-'):
            return _test_stability_model(model, api_key_value)
        else:
            return False, f"Unknown model provider for {model}"
    except Exception as e:
        app.logger.error(f"Error testing model {model}: {str(e)}")
        return False, str(e)


def _test_openai_model(model, api_key):
    """Test OpenAI model with a minimal API call"""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # Make a minimal test call
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=10,
            temperature=0.5
        )
        
        app.logger.info(f"OpenAI model {model} test successful")
        return True, None
    except Exception as e:
        error_msg = str(e)
        app.logger.warning(f"OpenAI model {model} test failed: {error_msg}")
        return False, error_msg


def _test_anthropic_model(model, api_key):
    """Test Anthropic (Claude) model with a minimal API call"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        # List of Claude models to try (same as in llm_service.py)
        claude_models = [
            'claude-sonnet-4-20250514',
            'claude-opus-4',
            'claude-3-5-sonnet-20241022',
            'claude-3-5-haiku-20241022',
            'claude-3-opus-20240229',
            'claude-3-sonnet-20240229',
            'claude-3.5-sonnet-20240620',
            'claude-3-haiku-20240307'
        ]
        
        # Try the specified model first, then fallback to other available models
        try_models = [model] + [m for m in claude_models if m != model]
        
        last_error = None
        for try_model in try_models:
            try:
                response = client.messages.create(
                    model=try_model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "test"}]
                )
                
                app.logger.info(f"Anthropic model {model} test successful (using {try_model})")
                return True, None
            except Exception as e:
                last_error = str(e)
                app.logger.debug(f"Tried {try_model}: {last_error}")
                continue
        
        # If we get here, none of the models worked
        error_msg = f"No Claude models available. Last error: {last_error}"
        app.logger.warning(f"Anthropic model {model} test failed: {error_msg}")
        return False, error_msg
        
    except Exception as e:
        error_msg = str(e)
        app.logger.warning(f"Anthropic model {model} test failed: {error_msg}")
        return False, error_msg


def _test_gemini_model(model, api_key):
    """Test Google Gemini model with a minimal API call"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        # List of Gemini models to try (in order of preference)
        # Newer models first, with fallbacks to older versions
        gemini_models = [
            'gemini-2.0-flash',
            'gemini-2.0-flash-exp',
            'gemini-1.5-pro',
            'gemini-1.5-flash',
            'gemini-1.5-pro-latest',
            'gemini-1.5-flash-latest',
            'gemini-pro',  # Older model, may not work
            'gemini-1.0-pro',
        ]
        
        # Try the specified model first, then fallback to other available models
        try_models = [model] + [m for m in gemini_models if m != model]
        
        last_error = None
        for try_model in try_models:
            try:
                model_obj = genai.GenerativeModel(try_model)
                response = model_obj.generate_content("test", stream=False)
                
                app.logger.info(f"Gemini model {model} test successful (using {try_model})")
                return True, None
            except Exception as e:
                last_error = str(e)
                # Check if it's a 404 - if so, this model doesn't exist, try the next one
                if "404" in last_error or "not found" in last_error.lower():
                    app.logger.debug(f"Tried {try_model}: model not found")
                    continue
                # For other errors, might be temporary - still try next model
                app.logger.debug(f"Tried {try_model}: {last_error}")
                continue
        
        # If we get here, none of the models worked
        error_msg = f"No Gemini models available. Last error: {last_error}"
        app.logger.warning(f"Gemini model {model} test failed: {error_msg}")
        return False, error_msg
        
    except Exception as e:
        error_msg = str(e)
        app.logger.warning(f"Gemini model {model} test failed: {error_msg}")
        return False, error_msg


def _test_huggingface_model(model, api_key):
    """Test Hugging Face model with a minimal API call"""
    try:
        import requests
        
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "inputs": "test",
            "parameters": {"max_length": 50}
        }
        
        # Map model names to full Hugging Face repository paths
        model_mapping = {
            'llama2-70b': 'meta-llama/Llama-2-70b-chat-hf',
            'mixtral-8x7b': 'mistralai/Mixtral-8x7B-Instruct-v0.1',
            'mistral-7b': 'mistralai/Mistral-7B-Instruct-v0.3',
            'codellama-34b': 'codellama/CodeLlama-34b-Instruct-hf'
        }
        
        hf_model = model_mapping.get(model, model)
        
        # Use the new Hugging Face Inference Providers API endpoint
        url = f"https://router.huggingface.co/hf-inference/{hf_model}"
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        # Check for successful response (200) or rate limit (503 is expected during testing)
        if response.status_code == 200:
            app.logger.info(f"Hugging Face model {model} test successful")
            return True, None
        elif response.status_code == 503:
            # Model is loaded but rate limited - still accessible
            app.logger.info(f"Hugging Face model {model} is accessible (rate limited)")
            return True, None
        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
            app.logger.warning(f"Hugging Face model {model} test failed: {error_msg}")
            return False, error_msg
            
    except Exception as e:
        error_msg = str(e)
        app.logger.warning(f"Hugging Face model {model} test failed: {error_msg}")
        return False, error_msg


def _test_stability_model(model, api_key):
    """Test Stability AI model with a minimal API call"""
    try:
        import requests
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        
        # Test endpoint - just get account info
        url = "https://api.stability.ai/v1/user/account"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            app.logger.info(f"Stability model {model} test successful")
            return True, None
        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
            app.logger.warning(f"Stability model {model} test failed: {error_msg}")
            return False, error_msg
            
    except Exception as e:
        error_msg = str(e)
        app.logger.warning(f"Stability model {model} test failed: {error_msg}")
        return False, error_msg

# ==================== END MODEL SETTINGS API ====================

# ==================== RAG PIPELINE API ====================

@app.route('/api/rag/search', methods=['POST'])
def rag_search():
    """Search for relevant documents using semantic similarity"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        similarity_threshold = data.get('similarity_threshold', 0.7)
        max_results = data.get('max_results', 10)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Get user identity for filtering
        identity = get_user_identity()
        user_id = identity.get('user_id')
        
        # Initialize RAG service
        from rag_service_simple import SimpleRAGService
        rag_service = SimpleRAGService(openai_api_key=os.getenv('OPENAI_API_KEY'))
        
        # Search for similar chunks
        results = rag_service.search_similar_chunks(
            query=query,
            similarity_threshold=similarity_threshold,
            max_results=max_results,
            user_id=str(user_id) if user_id else None
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'results': results,
            'total_results': len(results)
        })
        
    except Exception as e:
        app.logger.error(f"Error in RAG search: {str(e)}")
        return jsonify({'error': f'RAG search failed: {str(e)}'}), 500

@app.route('/api/rag/process-document', methods=['POST'])
def rag_process_document():
    """Process a document to generate embeddings"""
    try:
        data = request.get_json()
        context_item_id = data.get('context_item_id')
        
        if not context_item_id:
            return jsonify({'error': 'Context item ID is required'}), 400
        
        # Get the context item
        from models import ContextItem
        context_item = ContextItem.query.get(context_item_id)
        
        if not context_item:
            return jsonify({'error': 'Context item not found'}), 404
        
        # Check access permissions
        identity = get_user_identity()
        if identity.get('user_id') and str(context_item.user_id) != str(identity['user_id']):
            return jsonify({'error': 'Access denied'}), 403
        
        if not context_item.content_text:
            return jsonify({'error': 'No content text available for processing'}), 400
        
        # Initialize RAG service
        from rag_service_simple import SimpleRAGService
        rag_service = SimpleRAGService(openai_api_key=os.getenv('OPENAI_API_KEY'))
        
        # Process the document
        success = rag_service.process_document(
            context_item_id=context_item_id,
            text=context_item.content_text,
            metadata={
                'document_name': context_item.name,
                'content_type': context_item.content_type,
                'created_at': context_item.created_at.isoformat() if context_item.created_at else None
            }
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Document processed successfully',
                'context_item_id': context_item_id
            })
        else:
            return jsonify({'error': 'Failed to process document'}), 500
        
    except Exception as e:
        app.logger.error(f"Error processing document: {str(e)}")
        return jsonify({'error': f'Document processing failed: {str(e)}'}), 500

@app.route('/api/rag/process-all', methods=['POST'])
def rag_process_all():
    """Process all unprocessed documents for the current user"""
    try:
        # Get user identity
        identity = get_user_identity()
        user_id = identity.get('user_id')
        
        # Initialize RAG service
        from rag_service_simple import SimpleRAGService
        rag_service = SimpleRAGService(openai_api_key=os.getenv('OPENAI_API_KEY'))
        
        # Process all documents
        result = rag_service.process_all_documents(user_id=str(user_id) if user_id else None)
        
        return jsonify({
            'success': result['success'],
            'message': f"Processed {result['processed_count']} documents",
            'stats': result
        })
        
    except Exception as e:
        app.logger.error(f"Error processing all documents: {str(e)}")
        return jsonify({'error': f'Batch processing failed: {str(e)}'}), 500

@app.route('/api/rag/get-context', methods=['POST'])
def rag_get_context():
    """Get relevant context for a query to include in AI response"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_context_length = data.get('max_context_length', 4000)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Get user identity
        identity = get_user_identity()
        user_id = identity.get('user_id')
        
        # Initialize RAG service
        from rag_service_simple import SimpleRAGService
        rag_service = SimpleRAGService(openai_api_key=os.getenv('OPENAI_API_KEY'))
        
        # Get context for the query
        context = rag_service.get_context_for_query(
            query=query,
            max_context_length=max_context_length,
            user_id=str(user_id) if user_id else None
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'context': context,
            'context_length': len(context)
        })
        
    except Exception as e:
        app.logger.error(f"Error getting context: {str(e)}")
        return jsonify({'error': f'Context retrieval failed: {str(e)}'}), 500

@app.route('/api/rag/process-single', methods=['POST'])
def rag_process_single():
    """Process a single document to avoid timeout issues"""
    try:
        data = request.get_json()
        context_item_id = data.get('context_item_id')
        
        if not context_item_id:
            return jsonify({'error': 'Context item ID is required'}), 400
        
        # Get the context item
        from models import ContextItem
        context_item = ContextItem.query.get(context_item_id)
        
        if not context_item:
            return jsonify({'error': 'Context item not found'}), 404
        
        # Check access permissions
        identity = get_user_identity()
        if identity.get('user_id') and str(context_item.user_id) != str(identity['user_id']):
            return jsonify({'error': 'Access denied'}), 403
        
        if not context_item.content_text:
            return jsonify({'error': 'No content text available for processing'}), 400
        
        # Initialize RAG service
        from rag_service_simple import SimpleRAGService
        rag_service = SimpleRAGService(openai_api_key=os.getenv('OPENAI_API_KEY'))
        
        # Process the document
        success = rag_service.process_document(
            context_item_id=context_item_id,
            text=context_item.content_text,
            metadata={
                'document_name': context_item.name,
                'content_type': context_item.content_type,
                'created_at': context_item.created_at.isoformat() if context_item.created_at else None
            }
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Document processed successfully',
                'context_item_id': context_item_id,
                'document_name': context_item.name
            })
        else:
            return jsonify({'error': 'Failed to process document'}), 500
        
    except Exception as e:
        app.logger.error(f"Error processing document: {str(e)}")
        return jsonify({'error': f'Document processing failed: {str(e)}'}), 500

# ==================== CONVERSATIONAL RAG API ====================

@app.route('/api/rag/process-conversation', methods=['POST'])
def rag_process_conversation():
    """Process a conversation to generate embeddings for semantic search"""
    try:
        data = request.get_json()
        conversation_id = data.get('conversation_id')
        
        if not conversation_id:
            return jsonify({'error': 'Conversation ID is required'}), 400
        
        # Get the conversation
        from models import Conversation
        conversation = Conversation.query.get(conversation_id)
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Check access permissions
        identity = get_user_identity()
        if identity.get('user_id') and str(conversation.user_id) != str(identity['user_id']):
            return jsonify({'error': 'Access denied'}), 403
        
        # Initialize enhanced RAG service
        from rag_service_enhanced import EnhancedRAGService
        rag_service = EnhancedRAGService(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            db_session=db.session
        )
        
        # Process the conversation
        success = rag_service.process_conversation(conversation_id)
        
        if success:
            # Also process all messages in the conversation
            result = rag_service.process_conversation_messages(conversation_id)
            
            return jsonify({
                'success': True,
                'message': 'Conversation processed successfully',
                'conversation_id': conversation_id,
                'conversation_title': conversation.title,
                'processed_messages': result.get('processed_count', 0),
                'total_messages': result.get('total_messages', 0)
            })
        else:
            return jsonify({'error': 'Failed to process conversation'}), 500
        
    except Exception as e:
        app.logger.error(f"Error processing conversation: {str(e)}")
        return jsonify({'error': f'Conversation processing failed: {str(e)}'}), 500

@app.route('/api/rag/process-all-conversations', methods=['POST'])
def rag_process_all_conversations():
    """Process all conversations for the current user"""
    try:
        # Get user identity
        identity = get_user_identity()
        user_id = identity.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User authentication required'}), 401
        
        # Initialize enhanced RAG service
        from rag_service_enhanced import EnhancedRAGService
        rag_service = EnhancedRAGService(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            db_session=db.session
        )
        
        # Process all user data
        result = rag_service.process_all_user_data(str(user_id))
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'All conversations processed successfully',
                'total_conversations': result.get('total_conversations', 0),
                'processed_conversations': result.get('processed_conversations', 0),
                'total_messages': result.get('total_messages', 0),
                'processed_messages': result.get('processed_messages', 0)
            })
        else:
            return jsonify({'error': result.get('error', 'Unknown error')}), 500
        
    except Exception as e:
        app.logger.error(f"Error processing all conversations: {str(e)}")
        return jsonify({'error': f'Batch processing failed: {str(e)}'}), 500

@app.route('/api/rag/search-conversations', methods=['POST'])
def rag_search_conversations():
    """Search conversations using semantic similarity"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        max_results = data.get('max_results', 10)
        similarity_threshold = data.get('similarity_threshold', 0.7)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Get user identity
        identity = get_user_identity()
        user_id = str(identity['user_id']) if identity.get('user_id') else None
        
        # Initialize enhanced RAG service
        from rag_service_enhanced import EnhancedRAGService
        rag_service = EnhancedRAGService(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            db_session=db.session
        )
        
        # Search conversations
        results = rag_service.search_conversations(
            query=query,
            user_id=user_id,
            similarity_threshold=similarity_threshold,
            max_results=max_results
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        app.logger.error(f"Error searching conversations: {str(e)}")
        return jsonify({'error': f'Conversation search failed: {str(e)}'}), 500

@app.route('/api/rag/search-messages', methods=['POST'])
def rag_search_messages():
    """Search messages using semantic similarity"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        max_results = data.get('max_results', 10)
        similarity_threshold = data.get('similarity_threshold', 0.7)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Get user identity
        identity = get_user_identity()
        user_id = str(identity['user_id']) if identity.get('user_id') else None
        
        # Initialize enhanced RAG service
        from rag_service_enhanced import EnhancedRAGService
        rag_service = EnhancedRAGService(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            db_session=db.session
        )
        
        # Search messages
        results = rag_service.search_messages(
            query=query,
            user_id=user_id,
            similarity_threshold=similarity_threshold,
            max_results=max_results
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        app.logger.error(f"Error searching messages: {str(e)}")
        return jsonify({'error': f'Message search failed: {str(e)}'}), 500

@app.route('/api/rag/search-all', methods=['POST'])
def rag_search_all():
    """Search across documents, conversations, and messages"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        max_results = data.get('max_results', 20)
        similarity_threshold = data.get('similarity_threshold', 0.65)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Get user identity
        identity = get_user_identity()
        user_id = str(identity['user_id']) if identity.get('user_id') else None
        
        # Initialize enhanced RAG service
        from rag_service_enhanced import EnhancedRAGService
        rag_service = EnhancedRAGService(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            db_session=db.session
        )
        
        # Search all sources
        results = rag_service.search_all(
            query=query,
            user_id=user_id,
            similarity_threshold=similarity_threshold,
            max_results=max_results
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'results': results,
            'total_results': len(results.get('all_results', [])),
            'messages_count': len(results.get('messages', [])),
            'conversations_count': len(results.get('conversations', [])),
            'documents_count': len(results.get('documents', []))
        })
        
    except Exception as e:
        app.logger.error(f"Error in comprehensive search: {str(e)}")
        return jsonify({'error': f'Search failed: {str(e)}'}), 500

# ==================== DYNAMIC MODEL MANAGEMENT API ====================

@app.route('/api/models', methods=['GET'])
def get_available_models():
    """Get list of available models (dynamic)"""
    try:
        # Load models from file
        models_file = os.path.join(app.instance_path, 'available_models.json')
        
        if os.path.exists(models_file):
            import json
            with open(models_file, 'r') as f:
                models = json.load(f)
            app.logger.info(f"Loaded models from file: {len(models)} models")
        else:
            # Create starter models if file doesn't exist
            models = create_starter_models()
            app.logger.info(f"Created starter models: {len(models)} models")
        
        # Ensure all models have a type property (defaulting to 'chat' if not specified)
        for model in models:
            if 'type' not in model:
                # Default to 'chat' for backwards compatibility
                model['type'] = 'chat'
        
        response = jsonify(models)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        app.logger.error(f"Error getting available models: {str(e)}")
        return jsonify({'error': 'Failed to get available models'}), 500

def get_model_identifier(model_name):
    """
    Get the actual API model identifier from the display name.
    Falls back to model_name if model_value is not found (backward compatibility).
    """
    try:
        models_file = os.path.join(app.instance_path, 'available_models.json')
        if os.path.exists(models_file):
            import json
            with open(models_file, 'r') as f:
                models = json.load(f)
            
            # Find the model by name
            for model in models:
                if model.get('name') == model_name:
                    # Return model_value if it exists, otherwise fallback to name
                    return model.get('model_value', model_name)
            
            # Model not found in list, return the original name
            app.logger.warning(f"Model '{model_name}' not found in available models, using name as identifier")
            return model_name
        else:
            # No models file, fallback to name
            return model_name
    except Exception as e:
        app.logger.error(f"Error resolving model identifier for '{model_name}': {e}")
        # On error, fallback to using the name directly
        return model_name

def create_starter_models():
    """Create a set of starter models for new installations"""
    starter_models = [
        # OpenAI Models
        {'name': 'GPT-3.5 Turbo', 'model_value': 'gpt-3.5-turbo', 'provider': 'OpenAI', 'api_key': 'OPENAI_API_KEY', 'description': 'Fast and efficient for most tasks'},
        {'name': 'GPT-4', 'model_value': 'gpt-4', 'provider': 'OpenAI', 'api_key': 'OPENAI_API_KEY', 'description': 'Most capable GPT model'},
        {'name': 'GPT-4 Turbo', 'model_value': 'gpt-4-turbo', 'provider': 'OpenAI', 'api_key': 'OPENAI_API_KEY', 'description': 'Faster GPT-4 with longer context'},
        {'name': 'GPT-4o', 'model_value': 'gpt-4o', 'provider': 'OpenAI', 'api_key': 'OPENAI_API_KEY', 'description': 'Latest GPT-4 optimized model'},
        {'name': 'GPT-4o Mini', 'model_value': 'gpt-4o-mini', 'provider': 'OpenAI', 'api_key': 'OPENAI_API_KEY', 'description': 'Compact version of GPT-4o'},
        {'name': 'O1 Preview', 'model_value': 'o1-preview', 'provider': 'OpenAI', 'api_key': 'OPENAI_API_KEY', 'description': 'Advanced reasoning model'},
        {'name': 'O1 Mini', 'model_value': 'o1-mini', 'provider': 'OpenAI', 'api_key': 'OPENAI_API_KEY', 'description': 'Compact reasoning model'},
        
        # Anthropic Models
        {'name': 'Claude 3.5 Sonnet', 'model_value': 'claude-3-5-sonnet-20241022', 'provider': 'Anthropic', 'api_key': 'CLAUDE_API_KEY', 'description': 'Latest Claude model'},
        {'name': 'Claude 3 Opus', 'model_value': 'claude-3-opus-20240229', 'provider': 'Anthropic', 'api_key': 'CLAUDE_API_KEY', 'description': 'Most powerful Claude model'},
        {'name': 'Claude 3 Sonnet', 'model_value': 'claude-3-sonnet-20240229', 'provider': 'Anthropic', 'api_key': 'CLAUDE_API_KEY', 'description': 'Balanced Claude model'},
        {'name': 'Claude 3 Haiku', 'model_value': 'claude-3-haiku-20240307', 'provider': 'Anthropic', 'api_key': 'CLAUDE_API_KEY', 'description': 'Fastest Claude model'},
        
        # Google Models
        {'name': 'Gemini 2.0 Flash', 'model_value': 'gemini-2.0-flash', 'provider': 'Google', 'api_key': 'GEMINI_API_KEY', 'description': 'Latest fast Gemini model'},
        {'name': 'Gemini 1.5 Pro', 'model_value': 'gemini-1.5-pro', 'provider': 'Google', 'api_key': 'GEMINI_API_KEY', 'description': 'High-performance Gemini with long context'},
        {'name': 'Gemini 1.5 Flash', 'model_value': 'gemini-1.5-flash', 'provider': 'Google', 'api_key': 'GEMINI_API_KEY', 'description': 'Fast Gemini model'},
        
        # Hugging Face Models
        {'name': 'Llama 2 70B', 'model_value': 'llama2-70b', 'provider': 'Hugging Face', 'api_key': 'HUGGING_FACE_API_KEY', 'description': 'Large language model'},
        {'name': 'Mixtral 8x7B', 'model_value': 'mixtral-8x7b', 'provider': 'Hugging Face', 'api_key': 'HUGGING_FACE_API_KEY', 'description': 'Mixture of experts model'},
        {'name': 'Mistral 7B', 'model_value': 'mistral-7b', 'provider': 'Hugging Face', 'api_key': 'HUGGING_FACE_API_KEY', 'description': 'Fast and efficient Mistral model'},
        {'name': 'CodeLlama 34B', 'model_value': 'codellama-34b', 'provider': 'Hugging Face', 'api_key': 'HUGGING_FACE_API_KEY', 'description': 'Code generation model'},
        
        # Stability AI Models
    ]
    
    # Save starter models to file
    models_file = os.path.join(app.instance_path, 'available_models.json')
    os.makedirs(app.instance_path, exist_ok=True)
    
    import json
    with open(models_file, 'w') as f:
        json.dump(starter_models, f, indent=2)
    
    app.logger.info(f"Created starter models file with {len(starter_models)} models")
    return starter_models

@csrf.exempt
@app.route('/api/models', methods=['POST'])
def add_model():
    """Add a new model"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        name = data.get('name', '').strip()
        model_value = data.get('model_value', '').strip()
        provider = data.get('provider', '').strip()
        description = data.get('description', '').strip()
        api_key = data.get('api_key', '').strip()  # Custom API key name
        
        if not name or not provider:
            return jsonify({'error': 'Model name and provider are required'}), 400
        
        if not model_value:
            return jsonify({'error': 'Model identifier is required'}), 400
        
        # Load existing models
        models_file = os.path.join(app.instance_path, 'available_models.json')
        if os.path.exists(models_file):
            import json
            with open(models_file, 'r') as f:
                models = json.load(f)
        else:
            models = []
        
        # Check if model already exists
        if any(model['name'] == name for model in models):
            return jsonify({'error': f'Model {name} already exists'}), 400
        
        # Add new model
        new_model = {
            'name': name,
            'model_value': model_value,
            'provider': provider,
            'description': description or f'{provider} model'
        }
        
        # Add custom API key if provided
        if api_key:
            new_model['api_key'] = api_key
        
        models.append(new_model)
        
        # Save to file
        os.makedirs(app.instance_path, exist_ok=True)
        import json
        with open(models_file, 'w') as f:
            json.dump(models, f, indent=2)
        
        app.logger.info(f"Added model: {name} (identifier: {model_value}, provider: {provider}) with API key: {api_key or 'auto-detected'}")
        return jsonify({'success': True, 'model': new_model})
    
    except Exception as e:
        app.logger.error(f"Error adding model: {str(e)}")
        return jsonify({'error': 'Failed to add model'}), 500

@app.route('/api/models/<model_name>', methods=['DELETE'])
def remove_model(model_name):
    """Remove a model"""
    try:
        # Load existing models
        models_file = os.path.join(app.instance_path, 'available_models.json')
        if not os.path.exists(models_file):
            return jsonify({'error': 'No models file found'}), 404
        
        import json
        with open(models_file, 'r') as f:
            models = json.load(f)
        
        # Find and remove model
        original_count = len(models)
        models = [model for model in models if model['name'] != model_name]
        
        if len(models) == original_count:
            return jsonify({'error': f'Model {model_name} not found'}), 404
        
        # Save updated list
        with open(models_file, 'w') as f:
            json.dump(models, f, indent=2)
        
        app.logger.info(f"Removed model: {model_name}")
        return jsonify({'success': True, 'message': f'Model {model_name} removed'})
    
    except Exception as e:
        app.logger.error(f"Error removing model: {str(e)}")
        return jsonify({'error': 'Failed to remove model'}), 500

@app.route('/api/api-keys/status', methods=['GET'])
def get_api_key_status():
    """Get status of API keys (without exposing actual keys)"""
    try:
        # Check which API keys are configured in Railway environment
        api_keys = {
            'OPENAI_API_KEY': {
                'configured': bool(os.getenv('OPENAI_API_KEY', '').strip()),
                'provider': 'OpenAI',
                'models_supported': 'gpt-*, o1-*'
            },
            'CLAUDE_API_KEY': {
                'configured': bool(os.getenv('CLAUDE_API_KEY', '').strip()),
                'provider': 'Anthropic', 
                'models_supported': 'claude-*'
            },
            'GEMINI_API_KEY': {
                'configured': bool(os.getenv('GEMINI_API_KEY', '').strip()),
                'provider': 'Google',
                'models_supported': 'gemini-*'
            },
            'HUGGING_FACE_API_KEY': {
                'configured': bool(os.getenv('HUGGING_FACE_API_KEY', '').strip()),
                'provider': 'Hugging Face',
                'models_supported': 'llama*, mixtral*, codellama*'
            },
            'STABILITY_API_KEY': {
                'configured': bool(os.getenv('STABILITY_API_KEY', '').strip()),
                'provider': 'Stability AI',
                'models_supported': 'stable-*'
            }
        }
        
        app.logger.info(f"API key status check completed")
        return jsonify(api_keys)
    
    except Exception as e:
        app.logger.error(f"Error checking API key status: {str(e)}")
        return jsonify({'error': 'Failed to check API key status'}), 500

@app.route('/api/providers', methods=['GET'])
def get_providers():
    """Get list of supported providers"""
    try:
        providers = [
            {
                'name': 'OpenAI',
                'api_key': 'OPENAI_API_KEY',
                'model_patterns': ['gpt-*', 'o1-*'],
                'description': 'GPT models and O1 reasoning models'
            },
            {
                'name': 'Anthropic', 
                'api_key': 'CLAUDE_API_KEY',
                'model_patterns': ['claude-*'],
                'description': 'Claude family models'
            },
            {
                'name': 'Google',
                'api_key': 'GEMINI_API_KEY', 
                'model_patterns': ['gemini-*'],
                'description': 'Gemini models'
            },
            {
                'name': 'Hugging Face',
                'api_key': 'HUGGING_FACE_API_KEY',
                'model_patterns': ['llama*', 'mixtral*', 'codellama*'],
                'description': 'Open source models via Hugging Face'
            },
            {
                'name': 'Stability AI',
                'api_key': 'STABILITY_API_KEY',
                'model_patterns': ['stable-*'],
                'description': 'Image generation models'
            }
        ]
        
        return jsonify(providers)
    
    except Exception as e:
        app.logger.error(f"Error getting providers: {str(e)}")
        return jsonify({'error': 'Failed to get providers'}), 500

# ==================== END DYNAMIC MODEL MANAGEMENT API ====================

# ==================== PREFERENCES API ====================

@app.route('/api/preferences', methods=['GET'])
def get_preferences():
    """Get user preferences"""
    try:
        # Check if user is authenticated (but don't fail if auth is not available)
        user_id = None
        try:
            from auth import current_user_id
            user_id = current_user_id()
        except ImportError:
            # Auth module not available, continue without authentication
            pass
        
        # For now, allow access even without authentication for demo purposes
        # You can enhance this to require authentication in production
        
        # Load preferences from file
        preferences_file = os.path.join(app.instance_path, 'user_preferences.json')
        app.logger.info(f"Preferences file path: {preferences_file}")
        
        try:
            if os.path.exists(preferences_file):
                import json
                with open(preferences_file, 'r') as f:
                    preferences = json.load(f)
                app.logger.info(f"Loaded preferences from file: {preferences}")
            else:
                # Default preferences
                preferences = {
                    'defaultModel': 'gpt-3.5-turbo'  # Default to GPT-3.5 Turbo
                }
                app.logger.info(f"Using default preferences: {preferences}")
        except Exception as e:
            app.logger.error(f"Failed to load or create preferences: {str(e)}")
            # Return default preferences on error
            preferences = {
                'defaultModel': 'gpt-3.5-turbo'
            }
        
        return jsonify(preferences)
    
    except Exception as e:
        app.logger.error(f"Error getting preferences: {str(e)}")
        return jsonify({'error': 'Failed to get preferences'}), 500

@app.route('/api/preferences', methods=['POST'])
def save_preferences():
    """Save user preferences"""
    try:
        # Check if user is authenticated (but don't fail if auth is not available)
        user_id = None
        try:
            from auth import current_user_id
            user_id = current_user_id()
        except ImportError:
            # Auth module not available, continue without authentication
            pass
        
        # For now, allow access even without authentication for demo purposes
        # You can enhance this to require authentication in production
        
        preferences = request.get_json()
        if not preferences:
            return jsonify({'error': 'No preferences provided'}), 400
        
        app.logger.info(f"Received preferences: {preferences}")
        
        # Ensure instance path exists
        try:
            os.makedirs(app.instance_path, exist_ok=True)
            app.logger.info(f"Instance path: {app.instance_path}")
        except Exception as e:
            app.logger.error(f"Failed to create instance path: {str(e)}")
            return jsonify({'error': f'Failed to create instance path: {str(e)}'}), 500
        
        # Save preferences to file (you can enhance this to use database)
        preferences_file = os.path.join(app.instance_path, 'user_preferences.json')
        app.logger.info(f"Preferences file path: {preferences_file}")
        
        try:
            import json
            with open(preferences_file, 'w') as f:
                json.dump(preferences, f, indent=2)
        except Exception as e:
            app.logger.error(f"Failed to write preferences file: {str(e)}")
            return jsonify({'error': f'Failed to write preferences file: {str(e)}'}), 500
        
        app.logger.info(f"Preferences saved for user {user_id}")
        return jsonify({'success': True, 'message': 'Preferences saved successfully'})
    
    except Exception as e:
        app.logger.error(f"Error saving preferences: {str(e)}")
        return jsonify({'error': 'Failed to save preferences'}), 500

# ==================== END PREFERENCES API ====================

# ==================== TEMPLATE MANAGEMENT API ====================

from models import Template

@app.route('/api/templates', methods=['GET'])
def get_templates():
    """Get templates for current user + public templates"""
    try:
        # Get user identifier (session_id for free users, user_id for authenticated)
        user_identifier = session.get('user_id') or session.get('session_id')
        if not user_identifier:
            return jsonify({'error': 'User not identified'}), 401
        
        # Get user's templates + public templates
        user_templates = Template.query.filter(
            (Template.user_id == user_identifier) & 
            (Template.is_active == True)
        ).all()
        
        public_templates = Template.query.filter(
            (Template.is_public == True) & 
            (Template.is_active == True) &
            (Template.user_id != user_identifier)
        ).all()
        
        # Combine and format
        templates = {}
        for template in user_templates + public_templates:
            templates[str(template.id)] = {
                'name': template.name,
                'content': template.content,
                'category': template.category,
                'defaultModel': template.default_model,
                'description': template.description,
                'icon': template.icon,
                'usageCount': template.usage_count,
                'isPublic': template.is_public,
                'isUserOwned': template.user_id == user_identifier,
                'createdAt': template.created_at.isoformat() if template.created_at else None
            }
        
        return jsonify(templates)
        
    except Exception as e:
        app.logger.error(f"Error fetching templates: {str(e)}")
        return jsonify({'error': 'Failed to fetch templates'}), 500

@app.route('/api/templates', methods=['POST'])
def create_template():
    """Create a new template"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'content', 'category']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get user identifier
        user_identifier = session.get('user_id') or session.get('session_id')
        if not user_identifier:
            return jsonify({'error': 'User not identified'}), 401
        
        # Create template
        template = Template(
            user_id=user_identifier,
            name=data['name'],
            content=data['content'],
            category=data['category'],
            default_model=data.get('defaultModel'),
            description=data.get('description'),
            icon=data.get('icon', 'fas fa-file-alt'),
            is_public=data.get('isPublic', False)
        )
        
        db.session.add(template)
        db.session.commit()
        
        return jsonify({
            'id': str(template.id),
            'message': 'Template created successfully'
        }), 201
        
    except Exception as e:
        app.logger.error(f"Error creating template: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create template'}), 500

@app.route('/api/templates/<template_id>', methods=['PUT'])
def update_template(template_id):
    """Update an existing template"""
    try:
        data = request.get_json()
        
        # Get user identifier
        user_identifier = session.get('user_id') or session.get('session_id')
        if not user_identifier:
            return jsonify({'error': 'User not identified'}), 401
        
        # Find template (user must own it)
        template = Template.query.filter_by(
            id=template_id, 
            user_id=user_identifier
        ).first()
        
        if not template:
            return jsonify({'error': 'Template not found or access denied'}), 404
        
        # Update fields
        if 'name' in data:
            template.name = data['name']
        if 'content' in data:
            template.content = data['content']
        if 'category' in data:
            template.category = data['category']
        if 'defaultModel' in data:
            template.default_model = data['defaultModel']
        if 'description' in data:
            template.description = data['description']
        if 'icon' in data:
            template.icon = data['icon']
        if 'isPublic' in data:
            template.is_public = data['isPublic']
        if 'isActive' in data:
            template.is_active = data['isActive']
        
        template.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Template updated successfully'})
        
    except Exception as e:
        app.logger.error(f"Error updating template: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update template'}), 500

@app.route('/api/templates/<template_id>', methods=['DELETE'])
def delete_template(template_id):
    """Delete a template"""
    try:
        # Get user identifier
        user_identifier = session.get('user_id') or session.get('session_id')
        if not user_identifier:
            return jsonify({'error': 'User not identified'}), 401
        
        # Find template (user must own it)
        template = Template.query.filter_by(
            id=template_id, 
            user_id=user_identifier
        ).first()
        
        if not template:
            return jsonify({'error': 'Template not found or access denied'}), 404
        
        # Soft delete (mark as inactive)
        template.is_active = False
        template.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Template deleted successfully'})
        
    except Exception as e:
        app.logger.error(f"Error deleting template: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete template'}), 500

@app.route('/api/templates/<template_id>/usage', methods=['POST'])
def track_template_usage(template_id):
    """Track template usage (increment usage count)"""
    try:
        # Find template (can be any active template)
        template = Template.query.filter_by(
            id=template_id, 
            is_active=True
        ).first()
        
        if not template:
            return jsonify({'error': 'Template not found'}), 404
        
        # Increment usage count
        template.usage_count += 1
        template.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'usageCount': template.usage_count})
        
    except Exception as e:
        app.logger.error(f"Error tracking template usage: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to track usage'}), 500

# ==================== END TEMPLATE MANAGEMENT API ====================

# ==================== MULTI-USER SYSTEM INTEGRATION ====================

# Import user management modules
try:
    from user_models import User, Organization, UserSession, UserAuditLog, UserRole, UserStatus
    from auth_service import auth_service, AuthenticationError, AuthorizationError
    from user_api import user_bp
    from functools import wraps
    
    # Register user management blueprint
    app.register_blueprint(user_bp)
    
    # Add user context to all requests
    @app.before_request
    def load_user():
        """Load current user for each request"""
        try:
            g.current_user = auth_service.get_current_user()
        except Exception as e:
            app.logger.error(f"Error loading user: {str(e)}")
            g.current_user = None
    
    # Add user info to template context
    @app.context_processor
    def inject_user():
        """Inject user info into all templates"""
        return {
            'current_user': getattr(g, 'current_user', None),
            'user_roles': UserRole,
            'user_status': UserStatus
        }
    
    # Migration endpoint for upgrading to multi-user system
    @csrf.exempt
    @app.route('/migrate-user-system', methods=['GET', 'POST'])
    def migrate_user_system_endpoint():
        """Web endpoint to migrate to multi-user system"""
        try:
            if request.method == 'GET':
                return render_template('migration_info.html')
            
            # Run migration
            from migrate_user_system import migrate_to_multi_user_system
            result = migrate_to_multi_user_system()
            
            return jsonify(result), 200
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            app.logger.error(f"User system migration failed: {str(e)}")
            app.logger.error(f"Traceback:\n{error_traceback}")
            return jsonify({
                'success': False,
                'error': f'Migration failed: {str(e)}',
                'traceback': error_traceback
            }), 500
    
    app.logger.info("Multi-user system integration loaded successfully")
    
except ImportError as e:
    app.logger.warning(f"Multi-user system not available: {str(e)}")
    app.logger.info("Falling back to legacy authentication system")

# ==================== END MULTI-USER SYSTEM INTEGRATION ====================

@csrf.exempt
@app.route('/api/generate-diagram', methods=['POST'])
@limiter.limit("20 per minute")
@auth.access_required(allow_free=True)
def generate_diagram():
    """Generate an educational diagram/chart for a math problem using matplotlib"""
    try:
        data = request.get_json()
        if not data or not data.get('response'):
            return jsonify({'error': 'Response content is required'}), 400
        
        response_content = data['response']
        problem_context = data.get('problem', '')
        
        app.logger.info(f"Generating mathematical diagram for problem: {problem_context[:100]}")
        
        # Use MathVisualizer to generate the diagram
        from math_visualization import MathVisualizer
        visualizer = MathVisualizer()
        
        # Generate base64 encoded image
        image_base64 = visualizer.generate_diagram(problem_context, response_content)
        
        if not image_base64:
            return jsonify({'error': 'Failed to generate diagram'}), 500
        
        app.logger.info(f"Diagram generated successfully, size: {len(image_base64)} bytes")
        
        # Return the base64 image directly (no need to save to disk)
        return jsonify({
            'success': True,
            'image_data': f'data:image/png;base64,{image_base64}',
            'message': 'Educational diagram generated successfully',
            'diagram_type': 'math_visualization'
        }), 200
            
    except Exception as e:
        app.logger.error(f"Diagram generation error: {str(e)}", exc_info=True)
        return jsonify({'error': f'Failed to generate diagram: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)