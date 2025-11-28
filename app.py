from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, url_for, session, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf, validate_csrf
from config import Config
import uuid
from datetime import datetime, timedelta
import os
import re
import html
import hashlib
from werkzeug.utils import secure_filename
from sqlalchemy import text
import base64
from collections import OrderedDict

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

def build_math_guardrails_system_prompt(user_name, project):
    """Return strict math guardrails to reduce incorrect explanations for students.

    This prompt enforces: personalization, clear method choice, step structure,
    verification by substitution, discriminant sanity check, optional cross-check,
    realistic practical example, and a short comprehension question.
    """
    try:
        level = (project.math_level or '').strip() if project else ''
        subject = (project.math_subject or 'mathematics').strip() if project else 'mathematics'
    except Exception:
        level = ''
        subject = 'mathematics'
    level_clause = f" in {level}" if level else ''

    # Output style preference (default to clean plain text to avoid markup issues)
    try:
        identity = get_user_identity() or {}
        uid = identity.get('user_id')
        user_pref_plain = True  # default: plain text for clean copy/paste
        if uid:
            user_obj = User.query.get(uid)
            if user_obj and isinstance(getattr(user_obj, 'preferences', None), dict):
                prefs = user_obj.preferences
                if 'plain_text_output' in prefs:
                    user_pref_plain = bool(prefs.get('plain_text_output'))
                elif 'rich_math_output' in prefs:
                    # if rich requested explicitly, disable plain text
                    user_pref_plain = not bool(prefs.get('rich_math_output'))
    except Exception:
        user_pref_plain = True

    if user_pref_plain:
        return (
            f"You are an expert math tutor with a friendly, encouraging tone. You are assisting {user_name}. Use clear{level_clause} language. Your goal is to help the student understand how to solve the problem, not just give the answer.\n\n"
            "The Plan: Briefly state the strategy before solving.\n\n"
            "Step-by-Step Solution: Show all algebraic steps. Define new terms briefly. Use plain text only: no Markdown, no LaTeX, no code blocks. Math notation rules: fractions a/b; multiplication *; exponents x^2; roots sqrt(x); Greek letters as words (pi, theta).\n\n"
            "Images/OCR: If the user provided an image, first transcribe the math exactly in plain ASCII (a/b, x^2, sqrt(x)); do not solve until transcribed. If any symbol or number is unclear, ask for a one-line confirmation (e.g., 'Is it (36a^2+27a)/(3a)?').\n\n"
            "Verification: Compute first, then state the result. Substitute back to check. If any earlier stated value conflicts with the verified result, correct yourself explicitly and proceed with the verified value.\n\n"
            "Final Answer: Present the final simplified result in one short line.\n\n"
            "Teaching methods: Lines → y = m*x + b (start value b + steady change m). Find b by plugging a known point; intercepts by setting x=0 or y=0. Fraction division → Keep–Flip–Change.\n\n"
            "Examples policy: Provide a practical example when asked. If the exact numbers are awkward, you may use simpler numbers to illustrate the concept, but say it's an analogy. Never claim an inconsistent example matches the original.\n"
        )

    return (
        f"You are an expert math tutor with a friendly, encouraging tone. You are assisting {user_name}. Use clear{level_clause} language. Your goal is to help the student understand how to solve the problem, not just give the answer.\n\n"
        "## The Plan\n"
        "State the strategy briefly before solving (e.g., find slope, then use it to get the perpendicular line…).\n\n"
        "## Step-by-Step Solution\n"
        "Show all algebraic steps one by one. Explain why a step is taken if it isn't obvious. Define new terms in one sentence when first used (e.g., a reciprocal is 1 divided by a number; an intercept is where the line crosses an axis). Use LaTeX ($...$) for mathematical symbols and equations throughout.\n\n"
        "## Images/OCR\n"
        "If the user provided an image, first transcribe the math exactly in plain ASCII (a/b, x^2, sqrt(x)); do not solve until the transcription is written. If any symbol or number is unclear, ask for a one-line confirmation (e.g., 'Is it (36a^2+27a)/(3a)?').\n\n"
        "## Verification\n"
        "Compute first, then state the result. Plug the final answer back into the original problem to prove it works (e.g., substitute points into the line; check $m_1\cdot m_2=-1$ for perpendicular lines; substitute roots back to get 0). If any stated value conflicts with the verified result, correct yourself explicitly and continue with the verified value.\n\n"
        "## Final Answer\n"
        "Only now, present the final simplified result clearly.\n\n"
        "Formatting and tone:\n"
        "- Use Markdown headings (##) as above to structure the response.\n"
        "- Use LaTeX for variables, fractions, and equations (e.g., $y=mx+b$, $\\frac{a}{b}$).\n"
        "- Keep sentences short; use contractions when natural; be precise and age-appropriate.\n\n"
        "Teaching methods:\n"
        "- Lines: default to $y=mx+b$ (start value $b$ plus steady change $m$). Find $b$ by plugging a known point; find intercepts by setting $x=0$ or $y=0$. Avoid naming point-slope unless asked.\n"
        "- Fraction division: name and use Keep–Flip–Change (keep the first, flip the second, change $\\div$ to $\\times$).\n\n"
        "Examples policy:\n"
        "- Provide a practical example when asked. If the exact numbers are awkward, it's acceptable to use simpler numbers to illustrate the same concept, but say clearly that it's an analogy. Never present a numerically inconsistent example as if it matched the original.\n\n"
        "Follow-ups:\n"
        "- If the student asks for a simpler explanation, provide it immediately.\n"
        "- End with a natural check-in question only if it adds value (e.g., 'Does finding $b$ by plugging the point make sense?').\n"
    )

def build_user_profile_system_prompt(project=None):
    """Build a system prompt describing the currently logged-in user's profile.
    
    Optionally augmented by project-specific preferences. Project preferences
    override global preferences for this project.

    Uses session identity to fetch the User and includes any available
    preferences such as age, grade/year level, region, and learning style.
    """
    try:
        identity = get_user_identity() or {}
        user_id = identity.get('user_id')
        if not user_id:
            return None
        user = User.query.get(user_id)
        if not user:
            return None

        display_name = user.display_name or user.username or 'User'
        profile_bits = []

        # Collect optional details from preferences if present
        prefs = user.preferences or {}
        for key in ['age', 'gender', 'grade_level', 'year_level', 'school_year', 'region', 'learning_style', 'difficulty_preference']:
            value = prefs.get(key)
            if isinstance(value, str) and value.strip():
                profile_bits.append(f"{key.replace('_', ' ')}: {value.strip()}")
            elif isinstance(value, (int, float)):
                profile_bits.append(f"{key.replace('_', ' ')}: {value}")

        profile_line = ("; ".join(profile_bits)) if profile_bits else ""
        details = f"User profile: {profile_line}" if profile_line else ""
        # Try to infer age/level guidance
        age = None
        try:
            age = int(prefs.get('age')) if prefs.get('age') is not None else None
        except Exception:
            age = None
        age_clause = f" Aim for a reading level suitable for a {age}-year-old." if age else ""

        # Get global tone/verbosity/reading level
        tone = (prefs.get('tone') or '').strip() if isinstance(prefs.get('tone'), str) else ''
        verbosity = (prefs.get('verbosity') or '').strip() if isinstance(prefs.get('verbosity'), str) else ''
        reading_level = (prefs.get('reading_level') or '').strip() if isinstance(prefs.get('reading_level'), str) else ''
        
        # If project exists, merge project-specific preferences (project overrides global)
        project_id_str = None
        if project:
            try:
                project_id_str = str(project.id) if hasattr(project, 'id') else None
            except Exception:
                pass
        
        if project_id_str:
            project_profiles = prefs.get('project_profiles') or {}
            project_prefs = project_profiles.get(project_id_str) or {}
            # Project preferences override global
            if project_prefs.get('tone'):
                tone = str(project_prefs.get('tone')).strip()
            if project_prefs.get('verbosity'):
                verbosity = str(project_prefs.get('verbosity')).strip()
            if project_prefs.get('reading_level'):
                reading_level = str(project_prefs.get('reading_level')).strip()
            
            # Add project context note if project has specific preferences
            if project_prefs.get('verbosity') or project_prefs.get('tone'):
                project_name = getattr(project, 'name', 'this project')
                project_context = f" (Note: In this {project_name} project, user prefers {verbosity or 'standard'} verbosity)"
                details = details + project_context if details else project_context
        
        style_bits = []
        if tone:
            style_bits.append(f"tone: {tone}")
        if verbosity:
            style_bits.append(f"verbosity: {verbosity}")
        if reading_level:
            style_bits.append(f"reading_level: {reading_level}")
        style_clause = (" Style: " + ", ".join(style_bits) + ".") if style_bits else ""

        return (
            f"You are assisting {display_name}. Greet them by name once at the start; thereafter use their name sparingly and do not repeat greetings. "
            f"Use age-appropriate, clear language.{age_clause}{style_clause} Define new terms briefly when first used. Favor short sentences and concrete steps. "
            f"Provide teacher-quality explanations: precise, correct, and accessible; avoid filler. {details}"
        ).strip()
    except Exception:
        return None

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
# (Onboarding tour removed)

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
    'txt', 'pdf', 'docx', 'doc', 'csv', 'md',
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
    onboarding_done = True
    try:
        if auth.is_authenticated():
            user = User.query.get(session.get('user_id'))
            onboarding_done = bool(getattr(user, 'has_completed_onboarding', False)) if user else True
    except Exception:
        onboarding_done = True
    return render_template('app_main.html', USER_ONBOARDING_DONE=onboarding_done)

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
    
    # Purge demo guest on logout if enabled
    try:
        if os.getenv('DEMO_PURGE_ON_LOGOUT', 'false').lower() in ('1','true','yes','on'):
            uid = user_id
            from user_models import User
            user = User.query.filter(User.id == uid).first() if uid else None
            if user and isinstance(user.preferences, dict) and user.preferences.get('is_demo_guest'):
                # Delete user cascades to conversations/messages via FKs if configured; otherwise explicit cleanup is done elsewhere
                db.session.delete(user)
                db.session.commit()
                app.logger.info(f"Purged demo guest on logout: {uid}")
    except Exception as e:
        app.logger.warning(f"Demo purge on logout failed: {e}")

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


@csrf.exempt
@app.route('/auth/create-admin-user', methods=['POST'])
def create_admin_user():
    """Bootstrap a named admin user using the password-only admin session.
    Requires you to be logged in as the password-only admin (user_type=admin or SUPER_ADMIN).
    Body: { username, email, password }
    """
    try:
        # Ensure caller is the password-only admin/SUPER_ADMIN
        if not session.get('authenticated') or (session.get('user_type') != 'admin' and session.get('user_role') not in ['SUPER_ADMIN', 'super_admin']):
            return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json() or {}
        username = (data.get('username') or '').strip()
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''

        # Basic validations
        if not username or not email or not password:
            return jsonify({'error': 'username, email and password are required'}), 400
        if len(username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({'error': 'Invalid email format'}), 400
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400

        # Uniqueness
        if db.session.query(User).filter(User.username == username).first():
            return jsonify({'error': 'Username already exists'}), 400
        if db.session.query(User).filter(User.email == email).first():
            return jsonify({'error': 'Email already exists'}), 400

        # Create user with SUPER_ADMIN role
        new_user = User(username=username, email=email, password=password, role=UserRole.SUPER_ADMIN, status=UserStatus.ACTIVE, display_name=username)
        db.session.add(new_user)
        db.session.commit()

        try:
            audit_log = UserAuditLog(
                user_id=new_user.id,
                action='create_admin_user',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                success=True
            )
            db.session.add(audit_log)
            db.session.commit()
        except Exception:
            pass

        return jsonify({'success': True, 'message': 'Admin user created', 'user_id': str(new_user.id)})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Create admin user error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create admin user'}), 500

@csrf.exempt
@app.route('/auth/guest-login', methods=['POST'])
def guest_login():
    """Create an ephemeral demo guest and log them in when DEMO_MODE is enabled."""
    try:
        demo_mode = os.getenv('DEMO_MODE', 'false').lower() in ('1', 'true', 'yes', 'on')
        if not demo_mode:
            return jsonify({'error': 'Guest login disabled'}), 403

        import secrets, string
        # Generate a short unique username
        suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
        username = f"guest_{suffix}"
        password = secrets.token_urlsafe(12)
        email = f"{username}@example.invalid"

        # TTL for demo guest
        ttl_hours = int(os.getenv('DEMO_GUEST_TTL_HOURS', '4') or 4)
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

        # Create user with guest role
        user = User(
            username=username,
            email=email,
            password=password,
            role=UserRole.GUEST,
            status=UserStatus.ACTIVE,
            display_name='Guest'
        )
        prefs = user.preferences or {}
        prefs.update({'is_demo_guest': True, 'expires_at': expires_at.isoformat()})
        user.preferences = prefs
        db.session.add(user)
        db.session.commit()

        # Set session
        session['authenticated'] = True
        session['user_id'] = str(user.id)
        session['user_type'] = 'guest'
        session['user_role'] = UserRole.GUEST.value
        session['username'] = user.username
        session['display_name'] = user.display_name or 'Guest'

        # Audit log
        try:
            audit_log = UserAuditLog(
                user_id=user.id,
                action='guest_login',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                success=True,
                details={'expires_at': prefs['expires_at']}
            )
            db.session.add(audit_log)
            db.session.commit()
        except Exception as e:
            app.logger.debug(f"Guest login audit log failed: {e}")

        return jsonify({'success': True, 'username': user.username, 'display_name': session['display_name'], 'expires_at': prefs['expires_at']})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Guest login error: {e}")
        return jsonify({'error': 'Failed to create guest user'}), 500

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

@csrf.exempt
@app.route('/api/users/update-preferences', methods=['PUT'])
@auth.login_required
def update_user_preferences():
    """Update user preferences JSON with tone, verbosity, reading_level."""
    try:
        data = request.get_json() or {}
        prefs_in = (data.get('preferences') or {}) if isinstance(data.get('preferences'), dict) else {}
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401
        user = db.session.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        prefs = user.preferences or {}
        # Merge top-level simple keys
        for k in ('tone','verbosity','reading_level','adaptive_profile','voice_gender'):
            v = prefs_in.get(k)
            if v is None:
                continue
            if isinstance(v, str):
                prefs[k] = v.strip()
            else:
                prefs[k] = v
        # Merge nested profile if provided
        if isinstance(prefs_in.get('profile'), dict):
            prof = prefs.get('profile') or {}
            prof.update(prefs_in['profile'])
            prefs['profile'] = prof
        user.preferences = prefs
        from datetime import datetime
        user.last_activity_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'preferences': user.preferences})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating preferences: {e}")
        return jsonify({'error': 'Failed to update preferences'}), 500

@app.route('/api/users/preferences', methods=['GET'])
@auth.login_required
def get_user_preferences():
    """Return current user's preferences JSON."""
    try:
        user_id = session.get('user_id')
        if not user_id:
            # Allow password-only admin sessions to proceed with empty defaults
            if session.get('user_type') == 'admin' or session.get('user_role') in ['SUPER_ADMIN', 'super_admin']:
                return jsonify({'success': True, 'preferences': {}})
            return jsonify({'error': 'Not authenticated'}), 401
        user = db.session.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return jsonify({'success': True, 'preferences': user.preferences or {}})
    except Exception as e:
        app.logger.error(f"Error getting preferences: {e}")
        return jsonify({'error': 'Failed to get preferences'}), 500

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
    role_lower = str(identity.get('user_role') or '').lower()
    is_admin_flag = bool(identity.get('is_admin', False) or role_lower in ('admin', 'super_admin'))
    app.logger.info(f"get_projects - identity: {identity}, computed_is_admin: {is_admin_flag}")

    # Optional user_id filter (admin only)
    filter_user_id = request.args.get('user_id')
    if filter_user_id and not is_admin_flag:
        return jsonify({'error': 'User filtering is only available for admins'}), 403

    # Admin sees all projects (optionally filtered by user_id), regular users see only their own projects
    query = Project.query
    if is_admin_flag:
        # Admin can filter by user_id if provided
        if filter_user_id:
            try:
                filter_uuid = uuid.UUID(filter_user_id)
                query = query.filter(Project.owner_id == filter_uuid)
            except ValueError:
                return jsonify({'error': 'Invalid user_id format'}), 400
        # Otherwise admin sees all projects
    else:
        # Regular users see only projects they own
        user_id = identity.get('user_id')
        if user_id:
            query = query.filter(Project.owner_id == user_id)
        else:
            query = query.filter(False)  # No projects for invalid user_id
    
    projects = query.order_by(Project.created_at.desc()).all()
    
    project_data = []
    for project in projects:
        # Get owner information (for admin display)
        owner_info = None
        if is_admin_flag and project.owner_id:
            try:
                try:
                    from models import User
                except Exception:
                    from user_models import User
                owner = User.query.get(project.owner_id)
                if owner:
                    owner_info = {
                        'id': str(owner.id),
                        'username': owner.username,
                        'display_name': owner.display_name or owner.username
                    }
            except Exception:
                pass
        
        # Count conversations for this project
        # If admin and filter_user_id is set, also filter conversations by that user
        conv_query = db.session.query(Conversation).filter(Conversation.project_id == project.id)
        if is_admin_flag:
            if filter_user_id:
                try:
                    filter_uuid = uuid.UUID(filter_user_id)
                    conv_query = conv_query.filter(Conversation.user_id == filter_uuid)
                except ValueError:
                    pass
            # Admin sees all conversations when no filter
        else:
            # Regular users only see their own conversations
            conv_query = conv_query.filter(Conversation.user_id == identity.get('user_id'))
        
        conversation_count = conv_query.count()
        
        project_data.append({
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat() if project.updated_at else None,
            'conversation_count': conversation_count,
            'owner': owner_info  # Only populated for admin
        })
    
    return jsonify(project_data)

@app.route('/projects/<project_id>/clone', methods=['POST'])
@auth.login_required
def clone_project(project_id):
    """Clone a project (copy fields, exclude conversations)."""
    try:
        from models import Project
        source_uuid = uuid.UUID(project_id)
        source = Project.query.get_or_404(source_uuid)

        # Access control: owner or admin
        identity = get_user_identity()
        is_admin = identity.get('is_admin', False)
        user_id = identity.get('user_id')
        if not is_admin and str(source.owner_id) != str(user_id):
            return jsonify({'error': 'Access denied'}), 403

        # Generate a clone name
        base_name = source.name
        new_name = f"{base_name} (Copy)"

        # Create cloned project (no conversations attached)
        cloned = Project(
            name=new_name,
            description=source.description,
            agent_name=source.agent_name,
            agent_role=source.agent_role,
            agent_personality=source.agent_personality,
            primary_goal=source.primary_goal,
            goal_steps=source.goal_steps,
            rules_do=source.rules_do,
            rules_dont=source.rules_dont,
            context_background=source.context_background,
            user_role=source.user_role,
            output_format=source.output_format,
            persona_id=source.persona_id,
            math_level=source.math_level,
            math_subject=source.math_subject,
            learning_style=source.learning_style,
            difficulty_preference=source.difficulty_preference,
            owner_id=source.owner_id
        )

        db.session.add(cloned)
        db.session.commit()

        return jsonify({
            'id': str(cloned.id),
            'name': cloned.name,
            'description': cloned.description,
            'created_at': cloned.created_at.isoformat(),
            'updated_at': cloned.updated_at.isoformat() if cloned.updated_at else None
        }), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error cloning project: {e}")
        return jsonify({'error': 'Failed to clone project'}), 500

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
        app.logger.info(f"🔍 Initial is_math_project from frontend: {is_math_project}")
        
        # Try to determine if this is a math project
        # First, check the frontend's is_math_project flag
        if not is_math_project and (project_id or conversation_id):
            app.logger.info(f"🔍 Frontend says NOT math, trying to detect from DB: project_id={project_id}, conversation_id={conversation_id}")
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
                    app.logger.info(f"🔍 Fetching project from DB: project_id={project_id}")
                    try:
                        project_uuid = uuid.UUID(project_id)
                        project = Project.query.get(project_uuid)
                        if project:
                            app.logger.info(f"🔍 Found project: math_level={project.math_level}, math_subject={project.math_subject}")
                            is_math_project = bool(project.math_level or project.math_subject)
                            app.logger.info(f"✅ Detected math project from DB: is_math_project={is_math_project}")
                        else:
                            app.logger.info(f"❌ Project not found in DB")
                    except Exception as e:
                        app.logger.error(f"❌ Could not fetch project from DB: {e}")
                        import traceback
                        app.logger.error(traceback.format_exc())
                else:
                    app.logger.info(f"🔍 No project_id provided, cannot check DB")
            except Exception as e:
                app.logger.debug(f"Could not determine if math project: {e}")
        
        app.logger.info(f"Generating follow-up questions using model: {model}, is_math: {is_math_project}")
        app.logger.info(f"🔍 Follow-up question debugging: project_id={project_id}, conversation_id={conversation_id}, is_math_project={is_math_project}")
        
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
        
        # De-duplicate while preserving order
        seen = set()
        questions = [q for q in questions if not (q in seen or seen.add(q))]
        
        # For math projects, add targeted comprehension check instead of generic prompts
        app.logger.info(f"🔍 Checking if math project: is_math_project={is_math_project}")
        if is_math_project:
            # For math, include two math-specific prompts and three contextual prompts (max 5 total)
            younger_prompt = "Explain it to someone who is two years younger with less exposure to math"
            practical_prompt = "Give me a short, practical example of this in use that matches the same numbers or structure (no contrived or inconsistent scenarios)"
            contextual_prompts = [
                "Would you like to see an alternative method or a quick visual explanation?",
                "Why is it important to verify the result in the original equation?",
                "Try a similar problem to practice and check your steps",
                "Extension: if the numbers change slightly, can you predict how the intercepts/roots change without redoing all steps?"
            ]

            final_qs = []
            for p in [younger_prompt, practical_prompt] + contextual_prompts:
                if p not in final_qs:
                    final_qs.append(p)
                if len(final_qs) >= 5:
                    break
            for q in questions:
                if len(final_qs) >= 5:
                    break
                if q not in final_qs:
                    final_qs.append(q)
            questions = final_qs
        else:
            app.logger.info(f"❌ NOT a math project - not adding math-specific questions")
        
        # Cap per project type (math: 5, others: 2)
        max_followups = 5 if is_math_project else 2
        questions = questions[:max_followups]
        app.logger.info(f"Returning follow-up questions (max {max_followups}): {questions}")
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
    """Get conversations filtered by current user (authenticated or free user)
    
    Admin users can optionally filter by user_id query parameter.
    """
    try:
        # Import User model with fallback
        try:
            from models import User
        except Exception:
            from user_models import User
        project_id = request.args.get('project_id')
        filter_user_id = request.args.get('user_id')  # Optional user filter (admin only)

        # Get user identity
        identity = get_user_identity()
        role_lower = str(identity.get('user_role') or '').lower()
        is_admin_flag = bool(identity.get('is_admin', False) or role_lower in ('admin', 'super_admin'))
        app.logger.info(f"get_conversations - identity: {identity}, computed_is_admin: {is_admin_flag}, filter_user_id: {filter_user_id}")
        
        # Check if user_id filter is allowed (admin only)
        if filter_user_id and not is_admin_flag:
            return jsonify({'error': 'User filtering is only available for admins'}), 403
        
        # Start with base query
        if is_admin_flag:
            # Admin sees all conversations (optionally filtered by user_id)
            query = Conversation.query
            if filter_user_id:
                try:
                    filter_uuid = uuid.UUID(filter_user_id)
                    query = query.filter(Conversation.user_id == filter_uuid)
                    app.logger.info(f"Admin filtering conversations by user_id: {filter_user_id}")
                except ValueError as e:
                    app.logger.error(f"Invalid user_id format: {filter_user_id}, error: {e}")
                    return jsonify({'error': 'Invalid user_id format'}), 400
        else:
            # Regular users: use existing filter
            query = filter_conversations_by_user(Conversation.query)
        
        # Add project filter if specified
        if project_id:
            try:
                project_uuid = uuid.UUID(project_id)
                query = query.filter(Conversation.project_id == project_uuid)
            except ValueError:
                return jsonify({'error': 'Invalid project_id format'}), 400
        
        conversations = query.order_by(Conversation.updated_at.desc()).all()
        app.logger.info(f"Found {len(conversations)} conversations")

        # Build response safely
        response_data = []
        for conv in conversations:
            try:
                # Get user information (for admin display)
                user_info = None
                if identity.get('is_admin', False) and conv.user_id:
                    try:
                        user = User.query.get(conv.user_id)
                        if user:
                            user_info = {
                                'id': str(user.id),
                                'username': user.username,
                                'display_name': user.display_name or user.username
                            }
                    except Exception as e:
                        app.logger.debug(f"Error loading user info for conv {conv.id}: {e}")
                
                # Get message count safely (avoid lazy loading issues)
                try:
                    message_count = db.session.query(Message).filter(Message.conversation_id == conv.id).count()
                except Exception as e:
                    app.logger.debug(f"Error counting messages for conv {conv.id}: {e}")
                    message_count = 0
                
                response_data.append({
                    'id': str(conv.id),
                    'project_id': str(conv.project_id) if conv.project_id else None,
                    'title': conv.title,
                    'llm_model': conv.llm_model,
                    'created_at': conv.created_at.isoformat(),
                    'updated_at': conv.updated_at.isoformat(),
                    'tags': conv.tags or [],
                    'user': user_info,  # Only populated for admin
                    'message_count': message_count,
                    'attachment_count': len(conv.context_documents) if conv.context_documents else 0
                })
            except Exception as e:
                app.logger.error(f"Error processing conversation {conv.id if conv else 'unknown'}: {e}", exc_info=True)
                continue
        
        response = jsonify(response_data)
        
        # Set session cookie for free users
        if identity['type'] == 'free' and identity['session_id'] and not request.cookies.get('session_id'):
            response.set_cookie('session_id', identity['session_id'], max_age=30*24*60*60)  # 30 days
        
        return response
    except Exception as e:
        app.logger.error(f"Error in get_conversations: {e}", exc_info=True)
        return jsonify({'error': f'Failed to load conversations: {str(e)}'}), 500

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

@csrf.exempt
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
        
        app.logger.error(f"💬💬💬 CHAT ENDPOINT CALLED - conversation_id={conversation_id}, model={model}, message_length={len(user_message)}")  # ERROR level for visibility
        app.logger.info(f"💬 CHAT DEBUG: Received chat request - conversation_id={conversation_id}, model={model}")
        
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
        conversation = None  # Initialize to ensure it's always in scope
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
        # Build a dynamic user profile system prompt (based on the logged-in user)
        try:
            user_profile_prompt = build_user_profile_system_prompt(project=project)
            if user_profile_prompt:
                messages.append({'role': 'system', 'content': user_profile_prompt})
                app.logger.info("Applied user profile system prompt")
        except Exception as e:
            app.logger.debug(f"Could not build user profile prompt: {e}")
        
        # Always include concise Project Context when a project exists
        if project:
            try:
                project_context_lines = [
                    f"Project Name: {project.name}",
                    f"Description: {project.description or '(none)'}"
                ]
                # Selected key fields
                key_fields = []
                for label, value in [
                    ('Primary Goal', getattr(project, 'primary_goal', None)),
                    ('Agent Role', getattr(project, 'agent_role', None)),
                    ('Math Level', getattr(project, 'math_level', None)),
                    ('Math Subject', getattr(project, 'math_subject', None)),
                ]:
                    if value:
                        key_fields.append(f"- {label}: {value}")
                if key_fields:
                    project_context_lines.append("Key Fields:\n" + "\n".join(key_fields))
                messages.append({
                    'role': 'system',
                    'content': (
                        "Project Context (always available for this chat):\n" +
                        "\n".join(project_context_lines) +
                        "\n\nUse this project context to tailor your responses. Do not state that you lack access to project information."
                    )
                })
                app.logger.info("Applied always-on Project Context system prompt")
            except Exception as _e:
                pass

        # Apply project template if we have a project
        if project:
            project_system_prompt = build_project_system_prompt(project)
            if project_system_prompt:
                # Keep project system prompt distinct; user name is already provided above
                messages.append({'role': 'system', 'content': project_system_prompt})
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
            active_context = []  # Initialize to avoid NameError
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
            # Inject strict math guardrails to improve correctness and clarity for students
            try:
                guardrails = build_math_guardrails_system_prompt(user_display_name, project)
                if guardrails:
                    messages.append({'role': 'system', 'content': guardrails})
                    app.logger.info("Applied math guardrails system prompt")
            except Exception as e:
                app.logger.warning(f"Failed to apply math guardrails: {e}")

            app.logger.info(f"Math project detected ({project.name}), loading math curriculum from database")
            
            # Load math curriculum context items from database
            from models import ContextItem
            from sqlalchemy import text
            
            # Check database type and use appropriate JSON filtering
            try:
                # Try PostgreSQL JSONB syntax
                math_context_items = ContextItem.query.filter(
                    ContextItem.user_id == 'system',
                    ContextItem.is_active == True
                ).filter(
                    text("extra_data->>'category' = 'math'")
                ).all()
            except Exception as e:
                # Fallback: load all system items and filter in Python
                app.logger.warning(f"Database JSON filtering failed, using fallback: {e}")
                all_system_items = ContextItem.query.filter(
                    ContextItem.user_id == 'system',
                    ContextItem.is_active == True
                ).all()
                math_context_items = [
                    item for item in all_system_items 
                    if item.extra_data and item.extra_data.get('category') == 'math'
                ]
            
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

            # Prefer stronger math models by default (server-side safeguard)
            try:
                strong_math_models = {
                    'claude-3.5-sonnet', 'claude-3-5-sonnet-20241022', 'claude-3.5-sonnet-20241022',
                    'claude-sonnet-4-20250514', 'gpt-4o', 'gpt-4o-mini'
                }
                if model not in strong_math_models:
                    preferred = None
                    if getattr(llm_service, 'anthropic_available', False):
                        preferred = 'claude-3.5-sonnet-20241022'
                    elif os.getenv('OPENAI_API_KEY'):
                        preferred = 'gpt-4o'
                    if preferred:
                        app.logger.info(f"Overriding model for math project: {model} -> {preferred}")
                        model = preferred
            except Exception as e:
                app.logger.warning(f"Could not apply math model preference: {e}")
        
        # Process attachments and add their content to context
        app.logger.error(f"🔍🔍🔍 ATTACHMENT PROCESSING STARTED - conversation_id={conversation_id}")  # Using ERROR level to ensure visibility
        app.logger.info(f"🔍 ATTACHMENT DEBUG: Starting attachment processing - conversation_id={conversation_id}")
        if conversation_id:
            try:
                # Ensure conv_uuid is defined (it should be from earlier, but handle if not)
                try:
                    conv_uuid
                except NameError:
                    conv_uuid = uuid.UUID(conversation_id)
                    app.logger.info(f"🔍 ATTACHMENT DEBUG: Created conv_uuid={conv_uuid}")
                else:
                    app.logger.info(f"🔍 ATTACHMENT DEBUG: Using existing conv_uuid={conv_uuid}")
                
                # Get all attachments for this conversation
                # Try both methods: join with Message, and direct query via message relationship
                app.logger.info(f"🔍 ATTACHMENT DEBUG: Querying attachments with conv_uuid={conv_uuid}")
                conversation_attachments = Attachment.query.join(Message).filter(
                    Message.conversation_id == conv_uuid
                ).all()
                
                # Fallback: if no attachments found, try querying messages first then their attachments
                if not conversation_attachments:
                    app.logger.info(f"🔍 ATTACHMENT DEBUG: Join query found 0 attachments, trying fallback method")
                    messages_with_attachments = Message.query.filter_by(conversation_id=conv_uuid).all()
                    app.logger.info(f"🔍 ATTACHMENT DEBUG: Found {len(messages_with_attachments)} messages for conversation")
                    conversation_attachments = []
                    for msg in messages_with_attachments:
                        if msg.attachments:
                            app.logger.info(f"🔍 ATTACHMENT DEBUG: Message {msg.id} has {len(msg.attachments)} attachment(s)")
                            conversation_attachments.extend(msg.attachments)
                    app.logger.info(f"🔍 ATTACHMENT DEBUG: Fallback method found {len(conversation_attachments)} total attachment(s)")
                
                app.logger.error(f"🔍🔍🔍 ATTACHMENT QUERY RESULT: Found {len(conversation_attachments)} attachment(s) for conversation {conversation_id}")  # ERROR level
                app.logger.info(f"🔍 Found {len(conversation_attachments)} attachment(s) for conversation {conversation_id}")
                
                if conversation_attachments:
                    attachment_contents = []
                    for attachment in conversation_attachments:
                        try:
                            app.logger.info(f"📎 Processing attachment: {attachment.filename} (path: {attachment.file_path})")
                            
                            # Check if content is already processed
                            if attachment.processed_content:
                                app.logger.info(f"✅ Using cached content for {attachment.filename}")
                                content = attachment.processed_content
                            else:
                                # Extract content from file
                                # Try multiple path resolution strategies
                                file_path = None
                                possible_paths = [
                                    os.path.join(os.getcwd(), attachment.file_path),
                                    attachment.file_path,  # In case it's already absolute
                                    os.path.join(UPLOAD_FOLDER, os.path.basename(attachment.file_path))
                                ]
                                
                                for path_attempt in possible_paths:
                                    if os.path.exists(path_attempt):
                                        file_path = path_attempt
                                        app.logger.info(f"✅ Found file at: {file_path}")
                                        break
                                
                                if file_path and os.path.exists(file_path):
                                    try:
                                        with open(file_path, 'rb') as f:
                                            f.seek(0)  # Ensure we're at the beginning
                                            content = extract_document_content(f, attachment.filename)
                                        
                                        if content:
                                            app.logger.info(f"✅ Extracted {len(content)} characters from {attachment.filename}")
                                            # Cache the extracted content
                                            attachment.processed_content = content
                                            db.session.commit()
                                        else:
                                            app.logger.warning(f"⚠️ Extracted empty content from {attachment.filename}")
                                            content = f"[File: {attachment.filename} - Content extraction returned empty]"
                                    except Exception as extract_error:
                                        app.logger.error(f"❌ Extraction error for {attachment.filename}: {extract_error}", exc_info=True)
                                        content = f"[File: {attachment.filename} - Error during extraction: {str(extract_error)}]"
                                else:
                                    app.logger.error(f"❌ Attachment file not found. Tried paths: {possible_paths}")
                                    app.logger.error(f"   Current working directory: {os.getcwd()}")
                                    app.logger.error(f"   UPLOAD_FOLDER: {UPLOAD_FOLDER}")
                                    content = f"[File: {attachment.filename} - File not found on server]"
                            
                            if content:
                                attachment_contents.append({
                                    'filename': attachment.filename,
                                    'content': content
                                })
                                app.logger.info(f"✅ Added {attachment.filename} to attachment_contents (content length: {len(content)})")
                        except Exception as e:
                            app.logger.error(f"❌ Failed to process attachment {attachment.filename}: {e}", exc_info=True)
                            continue
                    
                    # Add attachment contents to context if we have any
                    # Always add attachments, even if active_context exists (they're different sources)
                    if attachment_contents:
                        app.logger.info(f"📤 Adding {len(attachment_contents)} attachment(s) to model context")
                        for att in attachment_contents:
                            system_msg = f"Document reference ({att['filename']}): You have access to this document content and can answer questions about it, count words, analyze it, or use it as guidelines:\n\n{att['content']}"
                            messages.insert(0, {
                                'role': 'system',
                                'content': system_msg
                            })
                            app.logger.info(f"✅ Added system message for {att['filename']} ({len(att['content'])} chars)")
                        app.logger.info(f"✅ Successfully added {len(attachment_contents)} attachment(s) to conversation context")
                        # Log the actual system messages being added
                        for i, msg in enumerate(messages[:len(attachment_contents)]):
                            if msg.get('role') == 'system' and 'Document reference' in msg.get('content', ''):
                                preview = msg['content'][:200] + '...' if len(msg['content']) > 200 else msg['content']
                                app.logger.info(f"📄 System message {i+1}: {preview}")
                    else:
                        app.logger.warning(f"⚠️ No attachment contents to add (all attachments failed processing?)")
                else:
                    app.logger.info(f"ℹ️ No attachments found for conversation {conversation_id}")
            except Exception as attachment_error:
                app.logger.error(f"❌ Failed to process attachments for conversation {conversation_id}: {attachment_error}", exc_info=True)
        
        # Log final message count and preview
        system_msg_count = sum(1 for msg in messages if msg.get('role') == 'system')
        app.logger.info(f"📊 Final message array: {len(messages)} total messages ({system_msg_count} system, {len(messages)-system_msg_count} conversation)")
        
        # Process context_documents (from /upload-context endpoint)
        # conversation is loaded at line 2557 if conversation_id exists, initialized to None above
        import json
        docs = None
        if conversation_id and conversation:
            # conversation is guaranteed to be loaded if conversation_id exists
            docs = getattr(conversation, 'context_documents', None)
        elif conversation_id:
            # Fallback: conversation wasn't loaded, load it now
            try:
                conv_uuid = uuid.UUID(conversation_id)
                conversation = Conversation.query.get_or_404(conv_uuid)
                docs = getattr(conversation, 'context_documents', None)
            except Exception as conv_error:
                app.logger.error(f"Failed to load conversation for context_documents: {conv_error}")
                docs = None
        
        if docs:
        if isinstance(docs, str):
            try:
                docs = json.loads(docs)
            except Exception:
                docs = []
            
            # Always process context_documents if they exist (they're a different source than active_context)
            if docs and isinstance(docs, list) and len(docs) > 0:
                app.logger.info(f"📄 Processing {len(docs)} context document(s) from conversation.context_documents")
            for doc in docs:
                    if doc and isinstance(doc, dict) and 'content' in doc:
                    task_type = doc.get('task_type', 'instructions')
                    filename = doc.get('filename', 'uploaded file')
                        content = doc.get('content', '')
                    
                        if content and len(content.strip()) > 0:  # Only add if content exists and is not empty
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
                            app.logger.info(f"✅ Added context_document {filename} to messages ({len(content)} chars)")
                        else:
                            app.logger.warning(f"⚠️ context_document {filename} has no content or empty content")
                processed_count = len([d for d in docs if d and isinstance(d, dict) and d.get('content') and len(d.get('content', '').strip()) > 0])
                app.logger.info(f"✅ Successfully processed {processed_count} context document(s) with content")
        
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
        
        # Log messages being sent to LLM (for debugging)
        system_msgs_with_attachments = [msg for msg in messages if msg.get('role') == 'system' and 'Document reference' in msg.get('content', '')]
        app.logger.info(f"📤 SENDING TO LLM: {len(messages)} messages total, {len(system_msgs_with_attachments)} attachment system messages")
        if system_msgs_with_attachments:
            for i, msg in enumerate(system_msgs_with_attachments):
                preview = msg['content'][:300] + '...' if len(msg['content']) > 300 else msg['content']
                app.logger.info(f"📄 Attachment system message {i+1} being sent: {preview}")
        
        # Get AI response and usage info - use model_identifier for API call
        ai_response, tokens, estimated_cost = llm_service.get_response(model_identifier, messages)

        # Adaptive profile update (lightweight EMA) based on this exchange
        try:
            identity = get_user_identity()
            current_user_id = identity.get('user_id')
            if current_user_id:
                user = User.query.get(current_user_id)
                if user is not None:
                    prefs = user.preferences or {}
                    profile = prefs.get('profile') or {}
                    
                    # Get learning signal from button click OR extract from message text
                    learning_signal = data.get('learning_signal', '').lower().strip()
                    project_id_str = str(project.id) if project and hasattr(project, 'id') else None
                    
                    # Detect signals (priority: explicit button signal > text detection)
                    delta_v = 0.0
                    if learning_signal:
                        # Button-based signals (explicit)
                        if learning_signal in ['explain_again', 'simplify', 'easier']:
                            delta_v -= 0.1  # User wants simpler = reduce verbosity
                        elif learning_signal in ['got_it', 'understood', 'clear']:
                            delta_v += 0.05  # User understood = slight increase (they're ready for more)
                        elif learning_signal in ['try_similar', 'another_example']:
                            delta_v += 0.03  # User wants practice = slight increase
                        elif learning_signal in ['more_detail', 'show_steps', 'explain_more']:
                            delta_v += 0.1  # User wants more detail = increase verbosity
                    else:
                        # Fallback: text-based signal detection (backwards compatible)
                        msg_lower = (user_message or '').lower()
                        simplify = any(k in msg_lower for k in ['simplify', 'explain again', 'easier'])
                        shorter = any(k in msg_lower for k in ['shorter', 'tl;dr'])
                        more_detail = any(k in msg_lower for k in ['more detail', 'step by step', 'show steps'])
                        if simplify or shorter: delta_v -= 0.1
                        if more_detail: delta_v += 0.1
                    
                    # EMA update function
                    def ema(old, delta, alpha=0.2, cap=0.05):
                        if delta > cap: delta = cap
                        if delta < -cap: delta = -cap
                        return max(0.0, min(1.0, (1-alpha)*old + alpha*(old+delta)))
                    
                    # Store per-project preferences if project exists, otherwise global
                    if project_id_str and prefs.get('adaptive_profile'):
                        # Initialize project_profiles structure if needed
                        project_profiles = prefs.get('project_profiles') or {}
                        project_prefs = project_profiles.get(project_id_str) or {}
                        
                        # Get existing verbosity score for this project (or global default)
                        v_old_global = float(profile.get('preferred_verbosity_score', 0.5) or 0.5)
                        v_old = float(project_prefs.get('preferred_verbosity_score', v_old_global) or v_old_global)
                        v_new = ema(v_old, delta_v)
                        project_prefs['preferred_verbosity_score'] = round(v_new, 3)
                        
                        # Update discrete verbosity for this project only
                        if v_new < 0.3: project_prefs['verbosity'] = 'brief'
                        elif v_new > 0.7: project_prefs['verbosity'] = 'detailed'
                        else: project_prefs['verbosity'] = 'standard'
                        
                        project_profiles[project_id_str] = project_prefs
                        prefs['project_profiles'] = project_profiles
                        app.logger.info(f"Updated project-specific verbosity for project {project_id_str}: {v_new:.3f}")
                    else:
                        # Global preference update (backwards compatible)
                        v_old = float(profile.get('preferred_verbosity_score', 0.5) or 0.5)
                        v_new = ema(v_old, delta_v)
                        profile['preferred_verbosity_score'] = round(v_new, 3)
                        prefs['profile'] = profile
                        # Only derive discrete verbosity if adaptive_profile is true and user did not set it explicitly
                        if prefs.get('adaptive_profile') and not prefs.get('verbosity'):
                            if v_new < 0.3: prefs['verbosity'] = 'brief'
                            elif v_new > 0.7: prefs['verbosity'] = 'detailed'
                            else: prefs['verbosity'] = 'standard'
                    
                    user.preferences = prefs
                    db.session.commit()
        except Exception as _adaptive_error:
            app.logger.debug(f"Adaptive profile update skipped: {_adaptive_error}")
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
    app.logger.error(f"📤📤📤 UPLOAD ENDPOINT CALLED - conversation_id={conversation_id}")  # ERROR level for visibility
    try:
        # Block uploads for demo guests
        try:
            uid = session.get('user_id')
            if uid:
                user = User.query.filter(User.id == uid).first()
                if user and isinstance(user.preferences, dict) and user.preferences.get('is_demo_guest'):
                    app.logger.error(f"❌ Upload blocked for demo guest user")
                    return jsonify({'error': 'Uploads are disabled for demo users'}), 403
        except Exception as e:
            app.logger.warning(f"Could not check demo guest status: {e}")
            pass
        conv_uuid = uuid.UUID(conversation_id)
        app.logger.info(f"📤 Upload: Valid conversation ID, conv_uuid={conv_uuid}")
    except ValueError as e:
        app.logger.error(f"❌ Upload: Invalid conversation ID: {conversation_id}, error: {e}")
        return jsonify({'error': 'Invalid conversation ID'}), 400
    conversation = Conversation.query.get_or_404(conv_uuid)
    app.logger.info(f"📤 Upload: Found conversation")
    
    if 'files' not in request.files:
        app.logger.error(f"❌ Upload: No 'files' key in request.files. Available keys: {list(request.files.keys())}")
        return jsonify({'error': 'No files part in the request'}), 400
    files = request.files.getlist('files')
    app.logger.info(f"📤 Upload: Got {len(files)} file(s) from request")
    if not files or files[0].filename == '':
        app.logger.error(f"❌ Upload: No files or empty filename. files={files}, first filename={files[0].filename if files else 'N/A'}")
        return jsonify({'error': 'No files selected'}), 400
    attachments = []
    try:
        for file in files:
            app.logger.info(f"📤 Processing file: {file.filename}, content_type: {file.content_type}")
            # Validate file
            if not file.filename:
                app.logger.error(f"❌ Upload: Empty filename")
                return jsonify({'error': 'Empty filename not allowed'}), 400
            
            if not allowed_file(file.filename):
                app.logger.error(f"❌ Upload: File type not allowed - {file.filename}. Allowed: {ALLOWED_EXTENSIONS}")
                return jsonify({'error': f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
            
            if not validate_file_size(file):
                app.logger.error(f"❌ Upload: File too large - {file.filename}")
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
            app.logger.info(f"✅ Upload: Saved file to {file_path}")
            
            # Extract content immediately (like /upload-context does)
            # This ensures content is available even if chat endpoint isn't called
            processed_content = None
            try:
                # Reopen file from disk for extraction (consistent with chat endpoint)
                with open(file_path, 'rb') as f:
                    processed_content = extract_document_content(f, filename)
                app.logger.info(f"✅ Upload: Extracted {len(processed_content)} characters from {filename}")
            except Exception as extract_error:
                app.logger.error(f"⚠️ Upload: Failed to extract content from {filename}: {extract_error}", exc_info=True)
                # Continue without content - attachment will still be created
                processed_content = None
            
            # Create a new message for the attachment (role='user', content='[file upload]')
            message = Message(
                conversation_id=conv_uuid,
                role='user',
                content=f'[File uploaded: {filename}]'
            )
            db.session.add(message)
            db.session.flush()  # Get message.id
            app.logger.info(f"✅ Upload: Created message with id={message.id}")
            attachment = Attachment(
                message_id=message.id,
                filename=filename,
                content_type=file.content_type,
                file_path=os.path.relpath(file_path, os.getcwd()),
                processed_content=processed_content,  # Store extracted content immediately
                created_at=datetime.utcnow()  # Ensure created_at is set
            )
            db.session.add(attachment)
            app.logger.info(f"✅ Upload: Created attachment with id={attachment.id}, file_path={attachment.file_path}, content_extracted={processed_content is not None}")
            attachments.append({
                'id': str(attachment.id),
                'filename': filename,
                'content_type': file.content_type,
                'file_path': attachment.file_path,
                'created_at': attachment.created_at.isoformat() if hasattr(attachment, 'created_at') else datetime.utcnow().isoformat()
            })
        db.session.commit()
        app.logger.info(f"✅ Upload: Successfully uploaded {len(attachments)} attachment(s) for conversation {conversation_id}")
        app.logger.error(f"📤📤📤 UPLOAD SUCCESS - {len(attachments)} file(s) uploaded")  # ERROR level for visibility
        return jsonify({'attachments': attachments}), 201
    except Exception as e:
        app.logger.error(f"❌❌❌ Attachment upload error: {e}", exc_info=True)  # ERROR level for visibility
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
            
            # Verify the data was saved by refreshing and checking
            db.session.refresh(conversation)
            saved_docs = conversation.context_documents
            app.logger.info(f"✅ Upload: Saved {filename} - context_documents count: {len(saved_docs) if saved_docs else 0}")
            if saved_docs:
                app.logger.info(f"✅ Upload: First doc has content: {bool(saved_docs[0].get('content') if saved_docs else False)}")
            
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

# ==================== ADMIN MATH PERSONAS/PROJECTS HELPERS ====================

@csrf.exempt
@app.route('/admin/ensure_math_personas', methods=['POST'])
@auth.login_required
def ensure_math_personas():
    """Admin-only: ensure the seven core math personas exist (upsert by name)."""
    try:
        identity = get_user_identity()
        role_lower = str(identity.get('user_role') or '').lower()
        is_admin_flag = bool(identity.get('is_admin', False) or role_lower in ('admin', 'super_admin'))
        if not is_admin_flag:
            return jsonify({'success': False, 'error': 'Admin access required'}), 403

        from models import Persona
        core_personas = [
            {
                'name': 'Number and Algebra',
                'agent_name': 'Algebra Guide',
                'role': 'A math tutor specializing in numbers, ratios, percentages and foundational algebra.',
                'traits': 'patient, precise, step-by-step, age-appropriate, checks understanding',
                'category': 'Mathematics',
                'description': 'Builds fluency with integers, fractions, ratios, indices, linear and quadratic basics.'
            },
            {
                'name': 'Functions and Graphs',
                'agent_name': 'Graph Coach',
                'role': 'A tutor focusing on functions, slopes, and graph interpretations.',
                'traits': 'visual, concrete examples, step-by-step, error-correcting',
                'category': 'Mathematics',
                'description': 'Linear, quadratic, exponential functions; slope, intercepts, transformations.'
            },
            {
                'name': 'Measurement and Geometry',
                'agent_name': 'Geometry Mentor',
                'role': 'A tutor for space, shape, and measurement problems.',
                'traits': 'visual, concise, builds intuition, step-by-step',
                'category': 'Mathematics',
                'description': 'Perimeter, area, volume, Pythagoras, trigonometry, angles, similarity, circles.'
            },
            {
                'name': 'Statistics and Probability',
                'agent_name': 'Stats Companion',
                'role': 'A tutor simplifying data, chance, and inference fundamentals.',
                'traits': 'clear language, real examples, avoids jargon, checks misconceptions',
                'category': 'Mathematics',
                'description': 'Displays, centre/spread, sampling, correlation, simple/compound and conditional probability.'
            },
            {
                'name': 'Financial Mathematics',
                'agent_name': 'Finance Helper',
                'role': 'A tutor connecting maths to everyday money decisions.',
                'traits': 'practical, step-by-step, real-life contexts',
                'category': 'Mathematics',
                'description': 'Budgeting, discounts, profit/loss, simple and compound interest.'
            },
            {
                'name': 'Discrete and Modelling',
                'agent_name': 'Modelling Coach',
                'role': 'A tutor for networks, scheduling, and optimisation modelling.',
                'traits': 'structured, explains assumptions, iterative',
                'category': 'Mathematics',
                'description': 'Networks, shortest paths, critical path, linear programming (intro), simulations.'
            },
            {
                'name': 'Extension / Pre-Calculus',
                'agent_name': 'Pre-Calculus Guide',
                'role': 'A tutor preparing students for higher-level mathematics.',
                'traits': 'rigorous but accessible, builds from intuition to formality',
                'category': 'Mathematics',
                'description': 'Polynomials, rationals, logs, trig graphs, identities, limits (conceptual).'
            }
        ]

        created = 0
        updated = 0
        for spec in core_personas:
            existing = Persona.query.filter(Persona.name == spec['name'], Persona.category == 'Mathematics').first()
            if existing:
                changed = False
                for k in ['agent_name', 'role', 'traits', 'description']:
                    if getattr(existing, k) != spec[k]:
                        setattr(existing, k, spec[k])
                        changed = True
                if changed:
                    existing.updated_at = datetime.utcnow()
                    updated += 1
            else:
                p = Persona(
                    name=spec['name'],
                    agent_name=spec['agent_name'],
                    role=spec['role'],
                    traits=spec['traits'],
                    category=spec['category'],
                    description=spec['description'],
                    created_by=str(identity.get('user_id') or 'admin')
                )
                db.session.add(p)
                created += 1

        db.session.commit()
        return jsonify({'success': True, 'created': created, 'updated': updated})
    except Exception as e:
        app.logger.error(f"ensure_math_personas error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to ensure personas'}), 500


@csrf.exempt
@app.route('/admin/create_math_projects_for_user', methods=['POST'])
@auth.login_required
def create_math_projects_for_user():
    """Admin-only: create one math project per core persona for the specified username (e.g., Molly)."""
    try:
        identity = get_user_identity()
        role_lower = str(identity.get('user_role') or '').lower()
        is_admin_flag = bool(identity.get('is_admin', False) or role_lower in ('admin', 'super_admin'))
        if not is_admin_flag:
            return jsonify({'success': False, 'error': 'Admin access required'}), 403

        data = request.get_json(silent=True) or {}
        # Import models, with fallback for User
        from models import Persona, Project
        try:
            from models import User  # Preferred if available
        except Exception:
            from user_models import User  # Fallback when User is defined in user_models.py
        # Import models, with fallback for User
        from models import Persona, Project
        try:
            from models import User
        except Exception:
            from user_models import User
        user = None
        user_id_str = (data.get('user_id') or '').strip()
        username = (data.get('username') or '').strip()
        if user_id_str:
            try:
                user_uuid = uuid.UUID(user_id_str)
                user = User.query.get(user_uuid)
            except Exception:
                return jsonify({'success': False, 'error': 'Invalid user_id format'}), 400
        elif username:
            user = User.query.filter_by(username=username).first()
        else:
            return jsonify({'success': False, 'error': 'username or user_id is required'}), 400

        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        personas = Persona.query.filter_by(category='Mathematics', is_active=True).all()
        if not personas:
            return jsonify({'success': False, 'error': 'No Math personas found. Run /admin/ensure_math_personas first.'}), 400

        created = 0
        skipped = 0
        results = []
        for persona in personas:
            # Safeguard field lengths to match Project schema
            project_name = f"{persona.name} – Math Project"
            if len(project_name) > 255:
                project_name = project_name[:255]
            agent_role_val = (persona.role or '')
            if len(agent_role_val) > 500:
                agent_role_val = agent_role_val[:500]
            agent_traits_val = (persona.traits or '')
            if len(agent_traits_val) > 500:
                agent_traits_val = agent_traits_val[:500]
            existing = Project.query.filter_by(owner_id=user.id, name=project_name).first()
            if existing:
                skipped += 1
                results.append({'project': project_name, 'status': 'exists'})
                continue

            proj = Project(
                name=project_name,
                description=f"Practice and coaching for {persona.name}.",
                agent_name=persona.agent_name,
                agent_role=agent_role_val,
                agent_personality=agent_traits_val,
                primary_goal=f"Help the student master {persona.name} with step-by-step guidance.",
                goal_steps='["diagnose level", "teach concept", "guided practice", "check understanding"]',
                rules_do='["be precise", "be age-appropriate", "check for understanding"]',
                rules_dont='["avoid jargon without explanation", "avoid hallucinations"]',
                context_background='',
                user_role='Student',
                output_format='plain_text',
                persona_id=persona.id,
                math_level='Year 9',
                math_subject=persona.name,
                learning_style='visual',
                difficulty_preference='standard',
                owner_id=user.id
            )
            db.session.add(proj)
            created += 1
            results.append({'project': project_name, 'status': 'created'})

        db.session.commit()
        return jsonify({'success': True, 'created': created, 'skipped': skipped, 'results': results})
    except Exception as e:
        app.logger.error(f"create_math_projects_for_user error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to create projects'}), 500


@csrf.exempt
@app.route('/admin/seed_math_subtopics_for_user', methods=['POST'])
@auth.login_required
def seed_math_subtopics_for_user():
    """Admin-only: create one conversation per subtopic in each Mathematics project for a user.
    - Accepts { user_id?: UUID, username?: str }
    - Skips creating a conversation if a conversation with the same title already exists in that project.
    - Conversation title = subtopic; initial user message = "Explain what is meant by {subtopic}."
    """
    try:
        identity = get_user_identity()
        role_lower = str(identity.get('user_role') or '').lower()
        is_admin_flag = bool(identity.get('is_admin', False) or role_lower in ('admin', 'super_admin'))
        if not is_admin_flag:
            return jsonify({'success': False, 'error': 'Admin access required'}), 403

        data = request.get_json(silent=True) or {}
        # Import User model with fallback
        try:
            from models import User
        except Exception:
            from user_models import User
        from models import Project, Conversation, Message

        # Resolve user
        user = None
        user_id_str = (data.get('user_id') or '').strip()
        username = (data.get('username') or '').strip()
        if user_id_str:
            try:
                user_uuid = uuid.UUID(user_id_str)
                user = User.query.get(user_uuid)
            except Exception:
                return jsonify({'success': False, 'error': 'Invalid user_id format'}), 400
        elif username:
            user = User.query.filter_by(username=username).first()
        else:
            return jsonify({'success': False, 'error': 'username or user_id is required'}), 400
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        # Subtopics by persona/project label
        topics = {
            'Number and Algebra': [
                'Integers and rational numbers',
                'Fractions, decimals, percentages',
                'Ratios and rates (unit rates, proportional reasoning)',
                'Indices and scientific notation',
                'Algebraic expressions and simplification',
                'Linear equations and inequalities',
                'Simultaneous equations',
                'Quadratic expressions and factorisation',
                'Quadratic equations (roots, completing the square)',
                'Sequences and series (arithmetic, geometric)'
            ],
            'Functions and Graphs': [
                'Cartesian coordinates and gradient',
                'Linear relationships (slope–intercept, point–slope)',
                'Quadratic functions (graphs, vertex form)',
                'Exponential functions and growth/decay',
                'Piecewise and absolute value functions',
                'Inverse and composite functions (intro)'
            ],
            'Measurement and Geometry': [
                'Perimeter, area (triangles, circles, composite shapes)',
                'Surface area and volume (prisms, cylinders, pyramids, cones, spheres)',
                "Pythagoras’ theorem and distance",
                'Trigonometry (sin, cos, tan in right triangles)',
                'Angle properties (parallel lines, polygons)',
                'Similarity and congruence',
                'Circles (chords, tangents, arcs)',
                'Coordinate geometry (midpoint, distance, gradient applications)'
            ],
            'Statistics and Probability': [
                'Data displays (dot plots, histograms, box plots)',
                'Measures of centre and spread (mean, median, mode, range, IQR, std dev)',
                'Sampling methods and bias',
                'Two-variable data (scatter plots, correlation, line of best fit)',
                'Probability basics (simple, compound events)',
                'Tree diagrams and Venn diagrams',
                'Conditional probability (intro)'
            ],
            'Financial Mathematics': [
                'Budgeting and financial planning',
                'Simple and compound interest',
                'Profit, loss, markup, discounts',
                'Tax, wages, superannuation (contextual projects)'
            ],
            'Discrete and Modelling': [
                'Networks and shortest paths (intro graph theory)',
                'Scheduling and critical path (intro)',
                'Linear programming (intro)',
                'Simulation and Monte Carlo (intro)',
                'Optimization projects (max/min under constraints)'
            ],
            'Extension / Pre-Calculus': [
                'Polynomial functions (beyond quadratics)',
                'Rational functions (asymptotes)',
                'Logarithms and exponent laws (deeper)',
                'Trigonometric graphs and identities (intro)',
                'Limits and average/instantaneous rate of change (conceptual intro)'
            ]
        }

        # Find user projects that match these persona labels
        user_projects = Project.query.filter_by(owner_id=user.id).all()
        # Accept both naming styles: exact persona name OR "{persona} – Math Project"
        def matches(persona_name: str, project_name: str) -> bool:
            return project_name == persona_name or project_name.startswith(persona_name + ' –')

        created = 0
        skipped = 0
        results = []
        for persona_name, subtopics in topics.items():
            # Pick the first matching project for this persona
            target = None
            for p in user_projects:
                if matches(persona_name, p.name):
                    target = p
                    break
            if not target:
                results.append({'persona': persona_name, 'status': 'no_project'})
                continue

            # Existing titles to prevent duplicates
            existing_titles = {c.title for c in Conversation.query.filter_by(project_id=target.id).all()}

            for sub in subtopics:
                title = sub[:255]
                if title in existing_titles:
                    skipped += 1
                    results.append({'persona': persona_name, 'project': target.name, 'topic': sub, 'status': 'skipped_exists'})
                    continue

                convo = Conversation(
                    project_id=target.id,
                    title=title,
                    llm_model='claude-3.5-sonnet-20241022',
                    user_id=user.id,
                    tags=['math', persona_name]
                )
                db.session.add(convo)
                db.session.flush()  # get convo.id

                msg = Message(
                    conversation_id=convo.id,
                    role='user',
                    content=f'Explain what is meant by {sub}.'
                )
                db.session.add(msg)

                created += 1
                results.append({'persona': persona_name, 'project': target.name, 'topic': sub, 'status': 'created'})

        db.session.commit()
        return jsonify({'success': True, 'created': created, 'skipped': skipped, 'results': results})
    except Exception as e:
        app.logger.error(f"seed_math_subtopics_for_user error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to seed subtopics'}), 500

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

@app.route('/api/conversation/<conversation_id>/attachments/debug', methods=['GET'])
@require_conversation_access
def debug_attachments(conversation_id):
    """Debug endpoint to inspect attachments for a conversation"""
    try:
        conv_uuid = uuid.UUID(conversation_id)
        conversation = Conversation.query.get_or_404(conv_uuid)
        
        # Get all messages for this conversation
        messages = Message.query.filter_by(conversation_id=conv_uuid).all()
        
        # Get attachments via join
        attachments_join = Attachment.query.join(Message).filter(
            Message.conversation_id == conv_uuid
        ).all()
        
        # Get attachments via message relationship
        attachments_via_msg = []
        for msg in messages:
            if msg.attachments:
                attachments_via_msg.extend(msg.attachments)
        
        # Check context_documents
        import json
        context_docs = conversation.context_documents
        context_docs_parsed = None
        if context_docs:
            if isinstance(context_docs, str):
                try:
                    context_docs_parsed = json.loads(context_docs)
                except:
                    context_docs_parsed = None
            else:
                context_docs_parsed = context_docs
        
        debug_info = {
            'conversation_id': str(conversation_id),
            'total_messages': len(messages),
            'attachments_via_join': len(attachments_join),
            'attachments_via_message': len(attachments_via_msg),
            'context_documents': {
                'exists': context_docs is not None,
                'type': type(context_docs).__name__ if context_docs else None,
                'count': len(context_docs_parsed) if context_docs_parsed else 0,
                'documents': []
            },
            'attachment_details': []
        }
        
        # Add context_documents details
        if context_docs_parsed:
            for i, doc in enumerate(context_docs_parsed):
                debug_info['context_documents']['documents'].append({
                    'index': i,
                    'filename': doc.get('filename', 'unknown'),
                    'task_type': doc.get('task_type', 'unknown'),
                    'has_content': bool(doc.get('content')),
                    'content_length': len(doc.get('content', '')) if doc.get('content') else 0,
                    'content_preview': doc.get('content', '')[:200] + '...' if doc.get('content') and len(doc.get('content', '')) > 200 else doc.get('content', '')
                })
        
        # Collect details for all attachments
        all_attachments = list(set(attachments_join + attachments_via_msg))
        for att in all_attachments:
            file_path = os.path.join(os.getcwd(), att.file_path)
            file_exists = os.path.exists(file_path)
            
            possible_paths = [
                os.path.join(os.getcwd(), att.file_path),
                att.file_path,
                os.path.join(UPLOAD_FOLDER, os.path.basename(att.file_path))
            ]
            
            found_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    found_path = path
                    break
            
            debug_info['attachment_details'].append({
                'id': str(att.id),
                'filename': att.filename,
                'file_path_stored': att.file_path,
                'file_exists': file_exists,
                'found_path': found_path,
                'has_processed_content': bool(att.processed_content),
                'processed_content_length': len(att.processed_content) if att.processed_content else 0,
                'message_id': str(att.message_id),
                'content_type': att.content_type,
                'created_at': att.created_at.isoformat() if att.created_at else None,
                'possible_paths': possible_paths,
                'current_working_dir': os.getcwd(),
                'upload_folder': UPLOAD_FOLDER
            })
        
        return jsonify({
            'success': True,
            'debug': debug_info
        })
    
    except Exception as e:
        app.logger.error(f"❌ Error in debug_attachments: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

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
    """Search conversations by content with project awareness (keyword) and optional semantic summaries"""
    try:
        query = request.args.get('query', '').strip()
        project_id = request.args.get('project_id')
        limit = int(request.args.get('limit', 20))
        use_semantic = request.args.get('semantic', 'false').lower() == 'true'
        
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
        
        response_payload = {
            'success': True,
            'query': query,
            'project_id': project_id,
            'total_results': len(results),
            'conversations': results
        }

        # Optional semantic search over summaries
        if use_semantic:
            try:
                from models import Conversation
                import numpy as np
                from rag_service_simple import RAGServiceSimple
                rag = RAGServiceSimple()
                q_emb = rag.generate_embedding(query)
                if q_emb:
                    qv = np.array(q_emb)
                    base_sem_q = filter_conversations_by_user(db.session.query(Conversation))
                    if project_id:
                        try:
                            project_uuid = uuid.UUID(project_id)
                            base_sem_q = base_sem_q.filter(Conversation.project_id == project_uuid)
                        except ValueError:
                            pass
                    sem_rows = base_sem_q.with_entities(Conversation.id, Conversation.title, Conversation.ai_summary, Conversation.summary_embedding).all()
                    scored = []
                    for cid, title, summ, emb in sem_rows:
                        if not emb:
                            continue
                        try:
                            v = np.array(emb)
                            sim = float(np.dot(qv, v) / (np.linalg.norm(qv) * np.linalg.norm(v)))
                            scored.append((sim, str(cid), title, summ))
                        except Exception:
                            continue
                    scored.sort(reverse=True, key=lambda x: x[0])
                    response_payload['semantic'] = [{ 'id': cid, 'title': title, 'ai_summary': summ or '', 'similarity': round(sim, 4) } for sim, cid, title, summ in scored[:10]]
            except Exception as se:
                app.logger.warning(f"Semantic summary search failed: {se}")

        return jsonify(response_payload)
        
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

@app.route('/api/visualize', methods=['POST'])
@auth.login_required
def visualize_response():
    try:
        data = request.get_json() or {}
        question = (data.get('question') or '').strip()
        response_text = (data.get('response') or '').strip()
        if not question and not response_text:
            return jsonify({'error': 'question or response is required'}), 400
        try:
            from math_visualization import MathVisualizer
            viz = MathVisualizer()
            img_b64 = viz.generate_diagram(question, response_text or question)
            if not img_b64:
                return jsonify({'error': 'Could not generate visualization'}), 422
            return jsonify({'success': True, 'visual': {'type': 'image/png;base64', 'data': img_b64}})
        except Exception as e:
            app.logger.error(f'Visualization error: {e}')
            return jsonify({'error': 'Visualization failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/tts', methods=['POST'])
def api_tts():
    try:
        data = request.get_json() or {}
        text_in = (data.get('text') or '').strip()
        voice_pref = (data.get('voice_gender') or '').strip().lower()
        if not text_in:
            return jsonify({'error': 'text is required'}), 400

        # Check feature flag in model settings
        try:
            from models import ModelSettings
            setting = ModelSettings.query.filter_by(model_name='cloud_tts').first()
            enabled = bool(setting.enabled) if setting else False
        except Exception:
            enabled = False
        if not enabled:
            return jsonify({'error': 'Cloud TTS disabled'}), 403

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return jsonify({'error': 'OpenAI API key not configured'}), 500

        # Choose voice best-effort
        voice = 'alloy'
        if voice_pref == 'male':
            voice = 'verse'
        elif voice_pref == 'female':
            voice = 'alloy'

        # Caching to reduce latency/cost for repeats
        global _TTS_CACHE
        try:
            _TTS_CACHE
        except NameError:
            _TTS_CACHE = OrderedDict()
        model_name = os.getenv('OPENAI_TTS_MODEL', 'tts-1')
        audio_format = os.getenv('OPENAI_TTS_FORMAT', 'opus')  # opus smaller/faster
        cache_key = f"{model_name}|{voice}|{audio_format}|{hashlib.sha256(text_in.encode('utf-8')).hexdigest()}"
        if cache_key in _TTS_CACHE:
            b64 = _TTS_CACHE[cache_key]
            # move to end (recently used)
            _TTS_CACHE.move_to_end(cache_key)
            return jsonify({'success': True, 'audio_base64': b64, 'content_type': 'audio/ogg' if audio_format=='opus' else 'audio/mpeg'})

        import requests
        url = 'https://api.openai.com/v1/audio/speech'
        payload = {
            'model': model_name,
            'input': text_in,
            'voice': voice,
            'format': audio_format
        }
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            return jsonify({'error': f'OpenAI TTS error {resp.status_code}', 'details': resp.text[:200]}), 502
        audio_bytes = resp.content
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        # Add to cache with simple LRU size cap
        _TTS_CACHE[cache_key] = audio_b64
        if len(_TTS_CACHE) > int(os.getenv('OPENAI_TTS_CACHE_SIZE', '100')):
            _TTS_CACHE.popitem(last=False)
        return jsonify({'success': True, 'audio_base64': audio_b64, 'content_type': 'audio/ogg' if audio_format=='opus' else 'audio/mpeg'})
    except Exception as e:
        app.logger.error(f"/api/tts error: {e}", exc_info=True)
        return jsonify({'error': 'TTS generation failed'}), 500

# ==================== PROGRESS SUMMARY API ====================
@app.route('/api/progress/summary', methods=['GET'])
@auth.login_required
def progress_summary():
    """Return per-topic progress summary and daily trends for the current user (or a target user if admin)."""
    try:
        # Determine user scope
        target_user_id = request.args.get('user_id')
        if not target_user_id:
            target_user_id = session.get('user_id')
        else:
            # Only allow specifying user_id if admin
            if session.get('user_role') not in ['super_admin', 'SUPER_ADMIN', 'admin']:
                return jsonify({'error': 'Forbidden'}), 403

        if not target_user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        # Time window
        window_param = (request.args.get('window') or '7d').lower()
        if window_param.endswith('d') and window_param[:-1].isdigit():
            window_days = int(window_param[:-1])
        else:
            window_days = 7

        # Core query to collect per-message topic data
        core_sql = text(
            """
            WITH msgs AS (
              SELECT m.id, m.role, m.content, m.timestamp, c.project_id,
                     date_trunc('day', m.timestamp)::date AS day
              FROM messages m
              JOIN conversations c ON c.id = m.conversation_id
              WHERE c.user_id = :user_id
                AND m.timestamp >= now() - (:window_days || ' days')::interval
            ),
            topics AS (
              SELECT msgs.*, COALESCE(p.math_subject, p.name, 'General') AS topic
              FROM msgs LEFT JOIN projects p ON p.id = msgs.project_id
            ),
            user_neg AS (
              SELECT topic,
                SUM( (position('simplify' in lower(content)) > 0)::int
                    + (position('explain again' in lower(content)) > 0)::int
                    + (position('shorter' in lower(content)) > 0)::int
                    + (position('tl;dr' in lower(content)) > 0)::int
                    + (position('step by step' in lower(content)) > 0)::int
                    + (position('show steps' in lower(content)) > 0)::int ) AS neg_count
              FROM topics WHERE role='user' GROUP BY topic
            ),
            assistant_neg AS (
              SELECT topic,
                SUM( (position('let me correct' in lower(content)) > 0)::int
                    + (position('i was wrong' in lower(content)) > 0)::int
                    + (position('correction' in lower(content)) > 0)::int ) AS neg_count
              FROM topics WHERE role='assistant' GROUP BY topic
            ),
            user_pos AS (
              SELECT topic,
                SUM( (position('try a similar problem' in lower(content)) > 0)::int
                    + (position('got it' in lower(content)) > 0)::int
                    + (position('i can do it' in lower(content)) > 0)::int ) AS pos_count
              FROM topics WHERE role='user' GROUP BY topic
            ),
            daily AS (
              SELECT topic, day, COUNT(*) AS q
              FROM topics WHERE role='user' GROUP BY topic, day
            )
            SELECT
              t.topic,
              COUNT(*) FILTER (WHERE t.role='user') AS questions,
              COALESCE(u.neg_count,0) + COALESCE(a.neg_count,0) AS neg_signals,
              COALESCE(p.pos_count,0) AS pos_signals
            FROM topics t
            LEFT JOIN user_neg u USING (topic)
            LEFT JOIN assistant_neg a USING (topic)
            LEFT JOIN user_pos p USING (topic)
            GROUP BY t.topic, u.neg_count, a.neg_count, p.pos_count
            ORDER BY questions DESC
            """
        )

        trend_sql = text(
            """
            WITH msgs AS (
              SELECT m.id, m.role, m.content, m.timestamp, c.project_id,
                     date_trunc('day', m.timestamp)::date AS day
              FROM messages m
              JOIN conversations c ON c.id = m.conversation_id
              WHERE c.user_id = :user_id
                AND m.timestamp >= now() - (:window_days || ' days')::interval
            ),
            topics AS (
              SELECT msgs.*, COALESCE(p.math_subject, p.name, 'General') AS topic
              FROM msgs LEFT JOIN projects p ON p.id = msgs.project_id
            )
            SELECT topic, day, COUNT(*) AS questions
            FROM topics
            WHERE role='user'
            GROUP BY topic, day
            ORDER BY topic, day
            """
        )

        rows = db.session.execute(core_sql, { 'user_id': str(target_user_id), 'window_days': window_days }).mappings().all()
        trend_rows = db.session.execute(trend_sql, { 'user_id': str(target_user_id), 'window_days': window_days }).mappings().all()

        # Build trend map topic -> [counts per day in order]
        from datetime import date, timedelta as td
        day_list = [ (date.today() - td(days=d)) for d in range(window_days-1, -1, -1) ]
        trend_map = {}
        for r in trend_rows:
            topic = r['topic']
            day = r['day']
            trend_map.setdefault(topic, {})[day] = int(r['questions'])
        topic_trends = {}
        for topic, per_day in trend_map.items():
            topic_trends[topic] = [ int(per_day.get(d, 0)) for d in day_list ]

        # Compute score and bucket
        topics = []
        total_q = 0
        latest_quiz = None
        total_quizzes = 0
        # Read durable quiz data from tables
        try:
            cnt_row = db.session.execute(text("SELECT COUNT(*) FROM quiz_attempts WHERE user_id = :uid"), { 'uid': str(target_user_id) }).first()
            total_quizzes = int(cnt_row[0]) if cnt_row else 0
            lrow = db.session.execute(text("SELECT project_id, score, correct, total_questions, time_taken_seconds, created_at FROM quiz_attempts WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1"), { 'uid': str(target_user_id) }).first()
            if lrow:
                latest_quiz = {
                    'project_id': str(lrow[0]) if lrow[0] else None,
                    'score': float(lrow[1]),
                    'correct': int(lrow[2]),
                    'total': int(lrow[3]),
                    'time_taken': int(lrow[4] or 0),
                    'at': lrow[5].isoformat() if lrow[5] else None
                }
        except Exception:
            pass
        # Per-topic mastery from quiz answers in the window
        quiz_signal_map = {}
        try:
            mastery_rows = db.session.execute(text("""
                SELECT qa.topic, SUM(qa.is_correct::int) AS pos, COUNT(*) AS total
                FROM quiz_answers qa
                JOIN quiz_attempts a ON a.id = qa.attempt_id
                WHERE a.user_id = :uid
                  AND a.created_at >= now() - (:window_days || ' days')::interval
                GROUP BY qa.topic
            """), { 'uid': str(target_user_id), 'window_days': window_days }).mappings().all()
            for mr in mastery_rows:
                quiz_signal_map[mr['topic'].lower()] = { 'pos': int(mr['pos'] or 0), 'neg': int((mr['total'] or 0) - (mr['pos'] or 0)) }
        except Exception:
            pass

        for r in rows:
            q = int(r['questions'] or 0)
            total_q += q
            neg = int(r['neg_signals'] or 0)
            pos = int(r['pos_signals'] or 0)
            # Quiz mastery fields
            qp = int((quiz_signal_map.get(r['topic'].lower()) or {}).get('pos', 0))
            qn = int((quiz_signal_map.get(r['topic'].lower()) or {}).get('neg', 0))
            qtot = qp + qn
            # Blend quiz signals for math topics
            tname = (r['topic'] or '').lower()
            math_keys = ['algebra','geometry','trig','prob','stat','surd','indice','measure','quadratic','straight','line','simultaneous','calculus']
            is_math_topic = any(k in tname for k in math_keys) and tname != 'general'
            if is_math_topic:
                pos += qp
                neg += qn
            # Compute score after blending
            score = max(0, min(100, 50 + pos*6 - neg*8))
            bucket = 'Strong' if score >= 70 else ('Stable' if score >= 40 else 'Improve')
            mastery = round((qp / qtot)*100) if qtot > 0 else None
            topics.append({
                'topic': r['topic'],
                'questions': q,
                'neg_signals': neg,
                'pos_signals': pos,
                'score': score,
                'bucket': bucket,
                'trend': topic_trends.get(r['topic'], [0]*window_days),
                'quiz_pos': qp,
                'quiz_neg': qn,
                'quiz_mastery': mastery
            })

        return jsonify({
            'windowDays': window_days,
            'totals': { 'questions': total_q, 'topics': len(topics), 'quizzes': total_quizzes },
            'topics': topics,
            'days': [ d.isoformat() for d in day_list ],
            'latestQuiz': latest_quiz
        })
    except Exception as e:
        app.logger.error(f"Progress summary error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to compute progress summary'}), 500

# ==================== PROGRESS: QUIZ HISTORY & DETAILS ====================
@app.route('/api/progress/quiz-history', methods=['GET'])
@auth.login_required
def progress_quiz_history():
    try:
        uid = session.get('user_id')
        if not uid:
            return jsonify({'error': 'Not authenticated'}), 401
        user_id = str(uid)
        window_arg = (request.args.get('window') or '30d').lower()
        limit = int(request.args.get('limit') or 10)
        limit = max(1, min(limit, 50))

        where = "a.user_id = :uid"
        params = { 'uid': user_id, 'limit': limit }
        if window_arg != 'all':
            # parse Nd
            try:
                days = int(window_arg.replace('d',''))
            except Exception:
                days = 30
            where += " AND a.created_at >= now() - (:days || ' days')::interval"
            params['days'] = days

        base_sql = f"""
            SELECT a.id, a.project_id, COALESCE(p.name,'Unknown') AS project_name,
                   a.score, a.correct, a.total_questions, a.time_taken_seconds, a.created_at
            FROM quiz_attempts a
            LEFT JOIN projects p ON p.id = a.project_id
            WHERE {where}
            ORDER BY a.created_at DESC
            LIMIT :limit
        """
        rows = db.session.execute(text(base_sql), params).mappings().all()
        attempt_ids = [ str(r['id']) for r in rows ]

        topics_map = {}
        if attempt_ids:
            # Build a safe parameterized IN clause
            placeholders = ", ".join([f":id{i}" for i in range(len(attempt_ids))])
            tsql = text(f"""
                SELECT qa.attempt_id::text AS attempt_id, qa.topic
                FROM quiz_answers qa
                WHERE qa.attempt_id IN ({placeholders})
            """)
            tparams = { f"id{i}": attempt_ids[i] for i in range(len(attempt_ids)) }
            topics_rows = db.session.execute(tsql, tparams).mappings().all()
            for tr in topics_rows:
                topics_map.setdefault(tr['attempt_id'], set()).add((tr['topic'] or 'general').lower())

        # Stats
        stats_sql = f"""
            SELECT COUNT(*) AS attempts,
                   COALESCE(ROUND(AVG(a.score)*100)::int, 0) AS avg_score_pct,
                   COALESCE(ROUND(MAX(a.score)*100)::int, 0) AS best_pct,
                   COALESCE(ROUND(MIN(a.score)*100)::int, 0) AS worst_pct
            FROM quiz_attempts a
            WHERE {where}
        """
        stats_row = db.session.execute(text(stats_sql), params).first()

        attempts = []
        for r in rows:
            attempts.append({
                'attempt_id': str(r['id']),
                'project_id': str(r['project_id']) if r['project_id'] else None,
                'project_name': r['project_name'],
                'score_pct': int(round(float(r['score'] or 0) * 100)),
                'correct': int(r['correct'] or 0),
                'total': int(r['total_questions'] or 0),
                'time_taken': int(r['time_taken_seconds'] or 0),
                'created_at': r['created_at'].isoformat() if r['created_at'] else None,
                'topics': sorted(list(topics_map.get(str(r['id']), set())))
            })

        return jsonify({
            'attempts': attempts,
            'stats': {
                'attempts': int(stats_row[0] or 0) if stats_row else 0,
                'avg_score_pct': int(stats_row[1] or 0) if stats_row else 0,
                'best_pct': int(stats_row[2] or 0) if stats_row else 0,
                'worst_pct': int(stats_row[3] or 0) if stats_row else 0
            }
        })
    except Exception as e:
        app.logger.error(f"Quiz history error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load quiz history'}), 500

@app.route('/api/progress/quiz-attempt/<attempt_id>', methods=['GET'])
@auth.login_required
def progress_quiz_attempt_detail(attempt_id):
    try:
        uid = session.get('user_id')
        if not uid:
            return jsonify({'error': 'Not authenticated'}), 401
        # Attempt meta
        meta = db.session.execute(text(
            """
            SELECT a.id, a.user_id, a.project_id, COALESCE(p.name,'Unknown') AS project_name,
                   a.score, a.correct, a.total_questions, a.time_taken_seconds, a.created_at
            FROM quiz_attempts a
            LEFT JOIN projects p ON p.id = a.project_id
            WHERE a.id = :id AND a.user_id = :uid
            """
        ), { 'id': attempt_id, 'uid': str(uid) }).mappings().first()
        if not meta:
            return jsonify({'error': 'Not found'}), 404
        # Answers
        ans_rows = db.session.execute(text(
            """
            SELECT question_number, topic, question_text, student_answer, correct_answer, is_correct
            FROM quiz_answers
            WHERE attempt_id = :id
            ORDER BY question_number ASC
            """
        ), { 'id': attempt_id }).mappings().all()
        answers = [{
            'question_number': int(r['question_number'] or 0),
            'topic': (r['topic'] or 'general'),
            'question_text': r['question_text'] or '',
            'student_answer': r['student_answer'] or '',
            'correct_answer': r['correct_answer'] or '',
            'is_correct': bool(r['is_correct'])
        } for r in ans_rows]

        return jsonify({
            'attempt': {
                'attempt_id': str(meta['id']),
                'project_id': str(meta['project_id']) if meta['project_id'] else None,
                'project_name': meta['project_name'],
                'score_pct': int(round(float(meta['score'] or 0)*100)),
                'correct': int(meta['correct'] or 0),
                'total': int(meta['total_questions'] or 0),
                'time_taken': int(meta['time_taken_seconds'] or 0),
                'created_at': meta['created_at'].isoformat() if meta['created_at'] else None
            },
            'answers': answers
        })
    except Exception as e:
        app.logger.error(f"Quiz attempt detail error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load quiz attempt'}), 500

# ==================== USAGE ANALYTICS (TOKENS/COST) ====================
@app.route('/api/usage/by-model', methods=['GET'])
@auth.login_required
def usage_by_model():
    try:
        uid = session.get('user_id')
        if not uid:
            return jsonify({'error': 'Not authenticated'}), 401
        window_arg = (request.args.get('window') or '30d').lower()
        try:
            days = int(window_arg.replace('d','')) if window_arg != 'all' else None
        except Exception:
            days = 30
        params = { 'uid': str(uid) }
        if days is not None:
            params['days'] = days

        try:
            # Preferred path: normalized union of new and legacy tables
            sql = text("""
                WITH u AS (
                  SELECT l.model,
                         COALESCE(l.input_tokens,0) AS in_tokens,
                         COALESCE(l.output_tokens,0) AS out_tokens,
                         COALESCE(l.total_tokens, COALESCE(l.input_tokens,0)+COALESCE(l.output_tokens,0)) AS tokens,
                         CASE WHEN lower(l.model) LIKE 'claude%'
                              -- For Claude: ALWAYS recalculate (ignore stored cost_usd which may be wrong)
                              -- Claude pricing: $15/1M output tokens = $0.000015 per output token
                              THEN CASE WHEN l.output_tokens IS NOT NULL AND l.output_tokens > 0
                                        THEN l.output_tokens * 0.000015
                                        -- If output_tokens unavailable but total_tokens exists, estimate conservatively (assume 50% output)
                                        WHEN l.total_tokens IS NOT NULL AND l.total_tokens > 0
                                        THEN (l.total_tokens * 0.5) * 0.000015
                                        ELSE 0
                                   END
                              ELSE COALESCE(l.cost_usd,0)
                         END AS cost_usd,
                         l.created_at AS created_at,
                         l.user_id,
                         l.conversation_id
                  FROM llm_usage_log l
                  UNION ALL
                  SELECT l.model,
                         0 AS in_tokens,
                         0 AS out_tokens,
                         COALESCE(l.tokens,0) AS tokens,
                         CASE WHEN lower(l.model) LIKE 'claude%'
                              THEN COALESCE(l.tokens,0) * 0.000015  -- approx $15/1M output
                              ELSE COALESCE(l.estimated_cost,0)
                          END AS cost_usd,
                         l.timestamp AS created_at,
                         NULL::uuid AS user_id,
                         l.conversation_id
                  FROM llm_usage_logs l
                )
                SELECT u.model,
                       SUM(u.in_tokens)  AS in_tokens,
                       SUM(u.out_tokens) AS out_tokens,
                       SUM(u.tokens)     AS tokens,
                       ROUND(SUM(u.cost_usd)::numeric, 6) AS cost_usd
                FROM u
                LEFT JOIN conversations c ON c.id = u.conversation_id
                WHERE (c.user_id = :uid OR u.user_id = :uid)
                  {time_filter}
                GROUP BY u.model
                ORDER BY tokens DESC
            """.replace('{time_filter}', "AND u.created_at >= now() - (:days || ' days')::interval" if days is not None else ""))
            rows = db.session.execute(sql, params).mappings().all()
        except Exception:
            # Fallback: legacy table only
            legacy_sql = text("""
                SELECT l.model,
                       0 AS in_tokens,
                       0 AS out_tokens,
                       SUM(COALESCE(l.tokens,0)) AS tokens,
                       ROUND(SUM(COALESCE(l.estimated_cost,0))::numeric, 6) AS cost_usd
                FROM llm_usage_logs l
                LEFT JOIN conversations c ON c.id = l.conversation_id
                WHERE c.user_id = :uid {time_filter}
                GROUP BY l.model
                ORDER BY tokens DESC
            """.replace('{time_filter}', "AND l.timestamp >= now() - (:days || ' days')::interval" if days is not None else ""))
            rows = db.session.execute(legacy_sql, params).mappings().all()
        return jsonify({ 'window': window_arg, 'models': [dict(r) for r in rows] })
    except Exception as e:
        app.logger.error(f"usage_by_model error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to compute usage'}), 500

@app.route('/api/admin/usage/by-user', methods=['GET'])
@auth.login_required
def admin_usage_by_user():
    try:
        role = (session.get('user_role') or '').lower()
        if role not in ['admin', 'super_admin', 'super admin', 'owner']:
            return jsonify({'error': 'Admin only'}), 403
        window_arg = (request.args.get('window') or '30d').lower()
        limit = int(request.args.get('limit') or 50)
        limit = max(1, min(limit, 200))
        try:
            days = int(window_arg.replace('d','')) if window_arg != 'all' else None
        except Exception:
            days = 30
        params = { 'limit': limit }
        if days is not None:
            params['days'] = days
        try:
            admin_sql = text("""
                WITH u AS (
                  SELECT l.user_id, l.model,
                         COALESCE(l.total_tokens, COALESCE(l.input_tokens,0)+COALESCE(l.output_tokens,0)) AS tokens,
                         CASE WHEN lower(l.model) LIKE 'claude%'
                              -- For Claude: ALWAYS recalculate (ignore stored cost_usd which may be wrong)
                              -- Claude pricing: $15/1M output tokens = $0.000015 per output token
                              THEN CASE WHEN l.output_tokens IS NOT NULL AND l.output_tokens > 0
                                        THEN l.output_tokens * 0.000015
                                        -- If output_tokens unavailable but total_tokens exists, estimate conservatively (assume 50% output)
                                        WHEN l.total_tokens IS NOT NULL AND l.total_tokens > 0
                                        THEN (l.total_tokens * 0.5) * 0.000015
                                        ELSE 0
                                   END
                              ELSE COALESCE(l.cost_usd,0)
                         END AS cost_usd,
                         l.created_at AS created_at
                  FROM llm_usage_log l
                  UNION ALL
                  SELECT c.user_id, l.model,
                         COALESCE(l.tokens,0) AS tokens,
                         CASE WHEN lower(l.model) LIKE 'claude%'
                              THEN COALESCE(l.tokens,0) * 0.000015  -- Recalculate Claude: $15/1M output tokens
                              ELSE COALESCE(l.estimated_cost,0)
                         END AS cost_usd,
                         l.timestamp AS created_at
                  FROM llm_usage_logs l LEFT JOIN conversations c ON c.id = l.conversation_id
                )
                SELECT u.user_id, COALESCE(u2.username, 'unknown') AS username,
                       SUM(u.tokens) AS tokens,
                       ROUND(SUM(u.cost_usd)::numeric, 6) AS cost_usd
                FROM u LEFT JOIN users u2 ON u2.id = u.user_id
                WHERE 1=1 {time_filter}
                GROUP BY u.user_id, u2.username
                ORDER BY tokens DESC
                LIMIT :limit
            """.replace('{time_filter}', "AND u.created_at >= now() - (:days || ' days')::interval" if days is not None else ""))
            rows = db.session.execute(admin_sql, params).mappings().all()

            bsql = text("""
                WITH u AS (
                  SELECT l.user_id, l.model,
                         COALESCE(l.total_tokens, COALESCE(l.input_tokens,0)+COALESCE(l.output_tokens,0)) AS tokens,
                         CASE WHEN lower(l.model) LIKE 'claude%'
                              -- For Claude: ALWAYS recalculate (ignore stored cost_usd which may be wrong)
                              -- Claude pricing: $15/1M output tokens = $0.000015 per output token
                              THEN CASE WHEN l.output_tokens IS NOT NULL AND l.output_tokens > 0
                                        THEN l.output_tokens * 0.000015
                                        -- If output_tokens unavailable but total_tokens exists, estimate conservatively (assume 50% output)
                                        WHEN l.total_tokens IS NOT NULL AND l.total_tokens > 0
                                        THEN (l.total_tokens * 0.5) * 0.000015
                                        ELSE 0
                                   END
                              ELSE COALESCE(l.cost_usd,0)
                         END AS cost_usd,
                         l.created_at AS created_at
                  FROM llm_usage_log l
                  UNION ALL
                  SELECT c.user_id, l.model,
                         COALESCE(l.tokens,0) AS tokens,
                         CASE WHEN lower(l.model) LIKE 'claude%'
                              THEN COALESCE(l.tokens,0) * 0.000015  -- Recalculate Claude: $15/1M output tokens
                              ELSE COALESCE(l.estimated_cost,0)
                         END AS cost_usd,
                         l.timestamp AS created_at
                  FROM llm_usage_logs l LEFT JOIN conversations c ON c.id = l.conversation_id
                )
                SELECT u.user_id, COALESCE(u2.username, 'unknown') AS username, u.model,
                       SUM(u.tokens) AS tokens,
                       ROUND(SUM(u.cost_usd)::numeric, 6) AS cost_usd
                FROM u LEFT JOIN users u2 ON u2.id = u.user_id
                WHERE 1=1 {time_filter}
                GROUP BY u.user_id, u2.username, u.model
                ORDER BY tokens DESC
            """.replace('{time_filter}', "AND u.created_at >= now() - (:days || ' days')::interval" if days is not None else ""))
            breakdown = db.session.execute(bsql, params).mappings().all()
        except Exception:
            # Fallback legacy-only
            admin_sql_legacy = text("""
                SELECT c.user_id, COALESCE(u.username, 'unknown') AS username,
                       SUM(COALESCE(l.tokens,0)) AS tokens,
                       ROUND(SUM(COALESCE(l.estimated_cost,0))::numeric, 6) AS cost_usd
                FROM llm_usage_logs l
                LEFT JOIN conversations c ON c.id = l.conversation_id
                LEFT JOIN users u ON u.id = c.user_id
                WHERE 1=1 {time_filter}
                GROUP BY c.user_id, u.username
                ORDER BY tokens DESC
                LIMIT :limit
            """.replace('{time_filter}', "AND l.timestamp >= now() - (:days || ' days')::interval" if days is not None else ""))
            rows = db.session.execute(admin_sql_legacy, params).mappings().all()
            breakdown_legacy = text("""
                SELECT c.user_id, COALESCE(u.username, 'unknown') AS username, l.model,
                       SUM(COALESCE(l.tokens,0)) AS tokens,
                       ROUND(SUM(COALESCE(l.estimated_cost,0))::numeric, 6) AS cost_usd
                FROM llm_usage_logs l
                LEFT JOIN conversations c ON c.id = l.conversation_id
                LEFT JOIN users u ON u.id = c.user_id
                WHERE 1=1 {time_filter}
                GROUP BY c.user_id, u.username, l.model
                ORDER BY tokens DESC
            """.replace('{time_filter}', "AND l.timestamp >= now() - (:days || ' days')::interval" if days is not None else ""))
            breakdown = db.session.execute(breakdown_legacy, params).mappings().all()
        return jsonify({ 'window': window_arg, 'users': [dict(r) for r in rows], 'breakdown': [dict(b) for b in breakdown] })
    except Exception as e:
        app.logger.error(f"admin_usage_by_user error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to compute admin usage'}), 500
# ==================== QUIZ GENERATION & SUBMISSION ====================
@app.route('/projects/<project_id>/quiz/generate', methods=['POST'])
@auth.login_required
def generate_quiz(project_id):
    try:
        # Fetch project
        try:
            proj_uuid = uuid.UUID(project_id)
        except Exception:
            return jsonify({'error': 'Invalid project id'}), 400
        project = Project.query.get(proj_uuid)
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        # Gather recent topics from conversations for this project
        topics_sql = text(
            """
            SELECT LOWER(COALESCE(p.math_subject, p.name, 'General')) AS topic,
                   COUNT(*) AS q
            FROM conversations c
            LEFT JOIN projects p ON p.id = c.project_id
            WHERE c.project_id = :pid
            GROUP BY topic
            ORDER BY q DESC
            LIMIT 5
            """
        )
        topic_rows = db.session.execute(topics_sql, { 'pid': str(project_id) }).mappings().all()
        topic_list = [r['topic'] for r in topic_rows] or [getattr(project, 'math_subject', None) or getattr(project, 'name', 'statistics')]

        # Build strict prompt for LLM: subject + year/age + difficulty
        raw_subject = getattr(project, 'math_subject', None) or getattr(project, 'name', None) or 'Mathematics'
        def normalize_subject(s: str) -> str:
            sl = (s or '').strip().lower()
            if any(k in sl for k in ['stat', 'data']):
                return 'statistics'
            if 'geom' in sl:
                return 'geometry'
            if 'trig' in sl or 'bearing' in sl:
                return 'trigonometry'
            if 'algebra' in sl or 'linear' in sl or 'equation' in sl or 'inequal' in sl:
                return 'algebra'
            if 'prob' in sl:
                return 'probability'
            if 'surd' in sl or 'indice' in sl or 'index' in sl:
                return 'indices_and_surds'
            if 'measure' in sl or 'area' in sl or 'volume' in sl or 'surface' in sl:
                return 'measurement'
            if 'quadratic' in sl or 'parabola' in sl:
                return 'quadratics'
            if 'straight line' in sl or 'graph' in sl or 'parallel' in sl or 'perpendicular' in sl:
                return 'straight_line_graphs'
            if 'simultaneous' in sl:
                return 'simultaneous_equations'
            return 'mathematics'
        subject_norm = normalize_subject(raw_subject)
        subject = {
            'statistics': 'Statistics',
            'geometry': 'Geometry',
            'trigonometry': 'Trigonometry',
            'algebra': 'Algebra',
            'probability': 'Probability',
            'indices_and_surds': 'Indices and Surds',
            'measurement': 'Measurement',
            'quadratics': 'Quadratics',
            'straight_line_graphs': 'Straight Line Graphs',
            'simultaneous_equations': 'Simultaneous Equations',
            'mathematics': 'Mathematics'
        }[subject_norm]

        level = getattr(project, 'math_level', None) or 'Year 10'
        # Derive student year/age context from project or user preferences
        student_year = level
        try:
            uid = session.get('user_id')
            usr = User.query.filter(User.id == uid).first() if uid else None
            if usr and isinstance(usr.preferences, dict):
                yl = usr.preferences.get('year_level') or usr.preferences.get('year')
                if isinstance(yl, str) and yl.strip():
                    student_year = yl
        except Exception:
            pass
        difficulty = getattr(project, 'difficulty_preference', 'Intermediate') or 'Intermediate'
        learning = getattr(project, 'learning_style', 'step by step') or 'step by step'
        # Recent question stems to avoid repeating
        recent_rows = db.session.execute(text(
            """
            SELECT qa.question_text
            FROM quiz_answers qa
            JOIN quiz_attempts a ON a.id = qa.attempt_id
            WHERE a.user_id = :uid AND a.project_id = :pid
            ORDER BY a.created_at DESC
            LIMIT 50
            """
        ), { 'uid': str(session.get('user_id')), 'pid': str(project_id) }).mappings().all()
        recent_stems = [ (r['question_text'] or '').strip() for r in recent_rows if (r.get('question_text') or '').strip() ]

        # Allowed topic hints per NSW Year 10 for better subject adherence
        allowed_by_subject = {
            'Statistics': ['central_tendency','distribution_shape','scatter_plots','correlation','sampling_methods','box_plots','quartiles'],
            'Geometry': ['basic_geometry','angles_parallel_lines','polygons','congruent_triangles','similar_triangles','circle_geometry','network_diagrams'],
            'Trigonometry': ['trig_ratios','unknown_angles','unknown_sides','2d_applications','bearings'],
            'Algebra': ['algebraic_fractions','linear_equations','inequalities','expanding','factorising'],
            'Probability': ['two_way_tables','venn_diagrams','complementary_events','tree_diagrams','independent_dependent'],
            'Indices and Surds': ['simplifying_surds','adding_subtracting_surds','multiplying_dividing_surds','rationalising_denominator','index_laws'],
            'Measurement': ['area','perimeter','surface_area','volume','accuracy','unit_conversion'],
            'Quadratics': ['expanding','factorising_monic','solving_by_factorising','parabolas'],
            'Straight Line Graphs': ['gradient','midpoint','length','parallel_perpendicular','equation_of_lines'],
            'Simultaneous Equations': ['substitution','elimination','problems']
        }
        allowed_topics = allowed_by_subject.get(subject, [])

        system_prompt = (
            f"Create a short quiz for a {student_year} NSW student in {subject}. "
            f"Difficulty: {difficulty}. Learning style: {learning}. "
            f"Only include topics within {subject}. Allowed topics: {', '.join(allowed_topics) if allowed_topics else 'subject-appropriate'}; DO NOT include out-of-subject items. "
            f"Return exactly 5 multiple-choice questions as strict JSON only, no prose. Each item must be: "
            f"{{'id': n, 'question': '...', 'type':'multiple_choice', 'options':['A','B','C','D'], 'correct_answer':'B', 'explanation':'...', 'topic':'<slug>'}}. "
            f"Use age-appropriate language for {student_year}. Topics to prioritize: {', '.join(topic_list[:3])}. "
            + (f"Avoid reusing these stems or near-duplicates: {recent_stems[:10]}. " if recent_stems else "")
            + "Vary wording so successive quizzes are not identical."
        )
        # Ask LLM for JSON
        messages = [
            { 'role': 'system', 'content': system_prompt },
            { 'role': 'user', 'content': 'Generate the quiz JSON now.' }
        ]
        model_identifier = get_model_identifier('gpt-4o') if os.getenv('OPENAI_API_KEY') else get_model_identifier('claude-3.5-sonnet-20241022')
        ai_response, _, _ = llm_service.get_response(model_identifier, messages)

        import json, random
        # Extract JSON from response (tolerant of extra text)
        try:
            start = ai_response.find('[')
            end = ai_response.rfind(']') + 1
            payload = ai_response[start:end]
            items = json.loads(payload)
        except Exception:
            # Fall back to empty item list; we'll fill from safe bank below
            items = []

        # Validate items and build a final set of 5
        validated = []
        used_questions = set()
        # Seed with a limited set of recent stems to avoid repeats
        for s in recent_stems[:20]:
            used_questions.add(s)
        # Randomize incoming items to encourage variety
        try:
            random.shuffle(items)
        except Exception:
            pass
        for i, it in enumerate(items[:5]):
            q = (it.get('question') or '').strip()
            opts = it.get('options') or []
            ans = (it.get('correct_answer') or '').strip()
            exp = (it.get('explanation') or '').strip()
            topic = (it.get('topic') or subject).strip().lower()
            # Basic repairs: accept 3–6 options; try to coerce correct if provided as index
            if isinstance(ans, int) and 0 <= ans < len(opts):
                ans = str(opts[ans])
            if not q or len(opts) < 3 or len(opts) > 8 or q in used_questions:
                continue
            if ans not in opts:
                # Try to recover from common key names
                alt = (it.get('answer') or it.get('correct') or '').strip()
                if alt and alt in opts:
                    ans = alt
                else:
                    continue
            used_questions.add(q)
            validated.append({
                'id': i+1,
                'question': q,
                'type': 'multiple_choice',
                'options': opts[:6],
                'correct_answer': ans,
                'explanation': exp,
                'topic': topic
            })
        # Fallback: top-up with safe templates if fewer than 5
        def fallback_items(subj: str):
            base = []
            subj_l = (subj or '').lower()
            if 'geom' in subj_l:
                base = [
                    {
                        'question': 'Which angle pair indicates lines are parallel?',
                        'options': ['Corresponding angles equal','Base angles equal','Sum of angles 100°','Right angles only'],
                        'correct_answer': 'Corresponding angles equal',
                        'explanation': 'Equal corresponding (or alternate interior) angles imply parallel lines.',
                        'topic': 'angles_parallel_lines'
                    },
                    {
                        'question': 'Two triangles have equal corresponding sides. This proves…',
                        'options': ['Similarity','Congruence','Right triangles','Isosceles triangles'],
                        'correct_answer': 'Congruence',
                        'explanation': 'SSS equality is a congruence condition.',
                        'topic': 'congruent_triangles'
                    },
                    {
                        'question': 'In similar triangles, the scale factor is 2. A side of length 5 cm becomes…',
                        'options': ['2.5 cm','5 cm','7 cm','10 cm'],
                        'correct_answer': '10 cm',
                        'explanation': 'Lengths scale by the factor: 5 × 2 = 10.',
                        'topic': 'similar_triangles'
                    },
                    {
                        'question': 'The sum of interior angles in a hexagon equals…',
                        'options': ['360°','540°','720°','900°'],
                        'correct_answer': '720°',
                        'explanation': '(n−2)×180 = 4×180 = 720° for n=6.',
                        'topic': 'polygons'
                    },
                    {
                        'question': 'A diameter AB subtends angle ACB on a circle. Angle ACB is…',
                        'options': ['90°','60°','45°','Depends on arc length'],
                        'correct_answer': '90°',
                        'explanation': 'Angle in a semicircle is a right angle.',
                        'topic': 'circle_geometry'
                    },
                    {
                        'question': 'Which transformation preserves shape and size?',
                        'options': ['Dilation','Reflection','Rotation','Shear'],
                        'correct_answer': 'Rotation',
                        'explanation': 'Rotations and reflections are isometries; dilation changes size.',
                        'topic': 'basic_geometry'
                    },
                    {
                        'question': 'In network diagrams, the shortest path problem seeks…',
                        'options': ['Minimum edges','Minimum total weight','Maximum flow','Eulerian trail'],
                        'correct_answer': 'Minimum total weight',
                        'explanation': 'Shortest path minimizes total edge weight between nodes.',
                        'topic': 'network_diagrams'
                    }
                ]
            elif 'trig' in subj_l:
                base = [
                    {
                        'question': 'sin(θ) = opposite / hypotenuse. For a right triangle, which is true?',
                        'options': ['sin²θ + cos²θ = 1','sinθ = adjacent/hyp','tanθ = hyp/opp','cosθ = opp/adj'],
                        'correct_answer': 'sin²θ + cos²θ = 1',
                        'explanation': 'Pythagorean identity holds for all θ.',
                        'topic': 'trig_ratios'
                    },
                    {
                        'question': 'Given a right triangle with hypotenuse 10 and angle 30°, the adjacent side is…',
                        'options': ['5','5√3','10','10√3'],
                        'correct_answer': '5√3',
                        'explanation': 'cos30° = √3/2, adjacent = 10×√3/2 = 5√3.',
                        'topic': 'unknown_sides'
                    }
                ]
            elif 'prob' in subj_l:
                base = [
                    {
                        'question': 'Two independent events A and B have P(A)=0.5 and P(B)=0.6. P(A∩B)=…',
                        'options': ['0.3','0.5','0.6','1.1'],
                        'correct_answer': '0.3',
                        'explanation': 'Independent ⇒ multiply: 0.5×0.6.',
                        'topic': 'independent_dependent'
                    }
                ]
            elif 'algebra' in subj_l or 'linear' in subj_l:
                base = [
                    {
                        'question': 'Solve 2x − 5 = 9.',
                        'options': ['x = 2','x = 5','x = 7','x = 14'],
                        'correct_answer': 'x = 7',
                        'explanation': '2x=14 ⇒ x=7.',
                        'topic': 'linear_equations'
                    },
                    {
                        'question': 'Simplify (x/3) + (2x/3).',
                        'options': ['x','2x/3','x/3','3x'],
                        'correct_answer': 'x',
                        'explanation': 'Same denominator, add numerators: 3x/3 = x.',
                        'topic': 'algebraic_fractions'
                    }
                ]
            elif 'stat' in subj_l:
                base = [
                    {
                        'question': 'Which measure of central tendency is most affected by extreme values?',
                        'options': ['Mean','Median','Mode','Range'],
                        'correct_answer': 'Mean',
                        'explanation': 'The mean shifts with large outliers more than median or mode.',
                        'topic': 'central_tendency'
                    },
                    {
                        'question': 'In a scatter plot with points trending upward, the correlation is likely…',
                        'options': ['Positive','Negative','Zero','Undefined'],
                        'correct_answer': 'Positive',
                        'explanation': 'Upward trend indicates positive correlation.',
                        'topic': 'correlation'
                    },
                    {
                        'question': 'A sample where every 5th person on a list is chosen is an example of…',
                        'options': ['Random sampling','Systematic sampling','Stratified sampling','Convenience sampling'],
                        'correct_answer': 'Systematic sampling',
                        'explanation': 'Selecting every k-th element is systematic sampling.',
                        'topic': 'sampling_methods'
                    },
                    {
                        'question': 'Which display best shows the relationship between two numerical variables?',
                        'options': ['Bar chart','Pie chart','Scatter plot','Box plot'],
                        'correct_answer': 'Scatter plot',
                        'explanation': 'Scatter plots compare pairs of numeric values.',
                        'topic': 'scatter_plots'
                    },
                    {
                        'question': 'If data are skewed right, which center is usually better to report?',
                        'options': ['Mean','Median','Mode','Midrange'],
                        'correct_answer': 'Median',
                        'explanation': 'Median is more robust to right-skewed outliers.',
                        'topic': 'distribution_shape'
                    },
                    {
                        'question': 'Which of the following best reduces sampling bias?',
                        'options': ['Voluntary response','Convenience sampling','Simple random sample','Using a large sample'],
                        'correct_answer': 'Simple random sample',
                        'explanation': 'Random selection reduces bias more than convenience or voluntary response.',
                        'topic': 'bias'
                    },
                    {
                        'question': 'Which statistic changes most when an outlier is added?',
                        'options': ['Median','Interquartile range','Mean','Mode'],
                        'correct_answer': 'Mean',
                        'explanation': 'Mean is sensitive to extreme values; median and IQR are more robust.',
                        'topic': 'outliers'
                    },
                    {
                        'question': 'A box plot shows a long whisker on the right. The distribution is…',
                        'options': ['Left-skewed','Right-skewed','Symmetric','Bimodal'],
                        'correct_answer': 'Right-skewed',
                        'explanation': 'A long right tail indicates right skew.',
                        'topic': 'box_plots'
                    },
                    {
                        'question': 'Correlation close to 0 implies…',
                        'options': ['No relationship','No linear relationship','Strong negative relationship','Strong positive relationship'],
                        'correct_answer': 'No linear relationship',
                        'explanation': 'There may still be a non-linear relationship even if correlation is near 0.',
                        'topic': 'correlation'
                    },
                    {
                        'question': 'In an experiment, the group that does not receive the treatment is called…',
                        'options': ['Experimental group','Control group','Placebo group','Random group'],
                        'correct_answer': 'Control group',
                        'explanation': 'Control group provides a baseline for comparison.',
                        'topic': 'experiments'
                    }
                ]
            else:
                base = [
                    {
                        'question': 'Which option is typically the most robust to outliers?',
                        'options': ['Mean','Median','Mode','Range'],
                        'correct_answer': 'Median',
                        'explanation': 'Median is less sensitive to extreme values.',
                        'topic': 'basics'
                    }
                ]
            # Avoid duplicates by question stem
            try:
                random.shuffle(base)
            except Exception:
                pass
            return [b for b in base if b['question'] not in used_questions]

        while len(validated) < 5:
            fb = fallback_items(subject)
            if not fb:
                break
            needed = 5 - len(validated)
            for add in fb[:needed]:
                used_questions.add(add['question'])
                validated.append({
                    'id': len(validated)+1,
                    'question': add['question'],
                    'type': 'multiple_choice',
                    'options': add['options'],
                    'correct_answer': add['correct_answer'],
                    'explanation': add['explanation'],
                    'topic': add['topic']
                })
        # If still short, relax duplicate block and fill from base bank (ensures success)
        if len(validated) < 5:
            fb_all = fallback_items(subject)
            i = 0
            while len(validated) < 5 and i < len(fb_all):
                add = fb_all[i]
                validated.append({
                    'id': len(validated)+1,
                    'question': add['question'],
                    'type': 'multiple_choice',
                    'options': add['options'],
                    'correct_answer': add['correct_answer'],
                    'explanation': add['explanation'],
                    'topic': add['topic']
                })
                i += 1
        if len(validated) != 5:
            # Final guarantee: fabricate simple neutral items
            while len(validated) < 5:
                n = len(validated)+1
                validated.append({
                    'id': n,
                    'question': f"Select the correct option (placeholder {n})",
                    'type': 'multiple_choice',
                    'options': ['A','B','C','D'],
                    'correct_answer': 'A',
                    'explanation': '',
                    'topic': (subject or 'general').lower()
                })
        return jsonify({'success': True, 'questions': validated})
    except Exception as e:
        app.logger.error(f"Quiz generate error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to generate quiz'}), 500

@app.route('/projects/<project_id>/quiz/submit', methods=['POST'])
@auth.login_required
def submit_quiz(project_id):
    try:
        data = request.get_json() or {}
        answers = data.get('answers') or []
        time_taken = int(data.get('time_taken') or 0)
        if not answers:
            return jsonify({'error': 'answers required'}), 400
        # Score
        total = len(answers)
        correct = sum(1 for a in answers if a.get('is_correct'))
        score = round(correct / total, 3)

        # Persist durable records to quiz_attempts and quiz_answers
        user_id = session.get('user_id')
        user = User.query.filter(User.id == user_id).first() if user_id else None
        if not user:
            return jsonify({'error': 'Not authenticated'}), 401

        attempt_id = str(uuid.uuid4())
        try:
            db.session.execute(
                text("""
                    INSERT INTO quiz_attempts (id, user_id, project_id, score, total_questions, correct, time_taken_seconds)
                    VALUES (:id, :user_id, :project_id, :score, :total_questions, :correct, :time_taken_seconds)
                """),
                {
                    'id': attempt_id,
                    'user_id': str(user.id),
                    'project_id': str(project_id),
                    'score': float(score),
                    'total_questions': int(total),
                    'correct': int(correct),
                    'time_taken_seconds': int(time_taken)
                }
            )
            for i, a in enumerate(answers, start=1):
                db.session.execute(
                    text("""
                        INSERT INTO quiz_answers (attempt_id, question_number, topic, question_text, student_answer, correct_answer, is_correct)
                        VALUES (:attempt_id, :qnum, :topic, :qtext, :student, :correct, :iscorrect)
                    """),
                    {
                        'attempt_id': attempt_id,
                        'qnum': int(a.get('id') or i),
                        'topic': (a.get('topic') or 'general').lower(),
                        'qtext': a.get('question') or '',
                        'student': a.get('student_answer') or '',
                        'correct': a.get('correct_answer') or '',
                        'iscorrect': bool(a.get('is_correct'))
                    }
                )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Quiz persistence error: {e}", exc_info=True)
            return jsonify({'error': 'Failed to persist quiz results'}), 500

        # Optional: also nudge preferences for adaptive profile (non-source-of-truth)
        try:
            prefs = user.preferences or {}
            quiz_signals = (prefs.get('quiz_signals') or {})
            proj_key = str(project_id)
            proj_map = quiz_signals.get(proj_key) or {}
            for a in answers:
                topic = (a.get('topic') or 'general').lower()
                entry = proj_map.get(topic) or {'pos': 0, 'neg': 0}
                if a.get('is_correct'):
                    entry['pos'] = int(entry.get('pos', 0)) + 1
                else:
                    entry['neg'] = int(entry.get('neg', 0)) + 1
                proj_map[topic] = entry
            quiz_signals[proj_key] = proj_map
            prefs['quiz_signals'] = quiz_signals
            user.preferences = prefs
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.warning('Preferences nudge for quiz signals failed; continuing')

        return jsonify({'success': True, 'score': score, 'correct': correct, 'total': total})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Quiz submit error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to submit quiz'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)