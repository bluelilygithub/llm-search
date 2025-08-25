from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, url_for, session
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

from PyPDF2 import PdfReader
import io
try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

# Initialize Flask app
app = Flask(__name__, static_folder='static')

# Configure app based on environment
from config import config
config_name = os.getenv('FLASK_CONFIG', 'default')
app.config.from_object(config[config_name])
config[config_name].init_app(app)

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

# CSRF protection is enabled globally
# Individual routes can be exempted using @csrf.exempt decorator

# Rate limiting - use in-memory for simplicity
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"]
)
limiter.init_app(app)

# Import models after db initialization
from models import Conversation, Message, Attachment, Project
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

# Import get_user_identity from security_utils to avoid duplication
from security_utils import get_user_identity

def filter_conversations_by_user(query):
    """Filter conversations by current user identity"""
    identity = get_user_identity()
    
    if identity['type'] == 'authenticated':
        # Authenticated user: only show conversations with their specific user_id
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
    return render_template('index.html')

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
    session.pop('authenticated', None)
    session.pop('user_id', None)
    return jsonify({'success': True, 'message': 'Logged out'})

@csrf.exempt  
@app.route('/auth/login', methods=['POST'])
def login_override():
    """Login endpoint - bypassing auth.py registration to add CSRF exemption"""
    from flask import session
    if not auth.is_auth_enabled():
        return jsonify({'success': True, 'message': 'Authentication disabled'})
    
    data = request.get_json()
    password = data.get('password', '')
    
    if auth.verify_password(password):
        session['authenticated'] = True
        session['user_id'] = 'admin'  # Simple single-user system
        return jsonify({'success': True, 'message': 'Login successful'})
    else:
        return jsonify({'success': False, 'error': 'Invalid password'}), 401

@app.route('/init-db')
def init_database():
    try:
        db.create_all()
        return jsonify({'message': 'Database initialized successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/projects', methods=['GET'])
@auth.login_required
def get_projects():
    from models import Project, Conversation
    projects = Project.query.order_by(Project.created_at.desc()).all()
    
    project_data = []
    for project in projects:
        # Count conversations for this project
        conversation_count = db.session.query(Conversation).filter(
            Conversation.project_id == project.id
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
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Project name is required'}), 400
    project = Project(
        name=data['name'],
        description=data.get('description', '')
    )
    db.session.add(project)
    db.session.commit()
    return jsonify({
        'id': str(project.id),
        'name': project.name,
        'description': project.description,
        'created_at': project.created_at.isoformat(),
        'updated_at': project.updated_at.isoformat() if project.updated_at else None
    }), 201

@csrf.exempt
@app.route('/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project and set related conversations to no project"""
    try:
        from models import Project, Conversation
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Set project_id to None for all related conversations
        Conversation.query.filter_by(project_id=project_id).update({'project_id': None})
        db.session.delete(project)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Project deleted'}), 200
    except Exception as e:
        app.logger.error(f"Error deleting project: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete project'}), 500

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
            'message_count': len(conv.messages)
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
    
    from models import Conversation
    conversation = Conversation(
        title=data['title'],
        llm_model=data['llm_model'],
        tags=data.get('tags', []),
        project_id=data.get('project_id'),
        user_id=identity['user_id'],
        session_id=identity['session_id'],
        ip_address=None  # IP address not needed for access control with unified identity system
    )
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
            'project_id': str(conversation.project_id) if conversation.project_id else None
        },
        'messages': [{
            'id': str(msg.id),
            'role': msg.role,
            'content': msg.content,
            'timestamp': msg.timestamp.isoformat()
        } for msg in messages]
    })

@app.route('/conversations/<conversation_id>', methods=['DELETE'])
@require_conversation_access
def delete_conversation(conversation_id):
    """Delete a conversation and all its messages"""
    try:
        conv_uuid = uuid.UUID(conversation_id)
        
        conversation = Conversation.query.get(conv_uuid)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Delete associated messages and attachments (cascade should handle this)
        db.session.delete(conversation)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Conversation deleted'}), 200
        
    except ValueError:
        return jsonify({'error': 'Invalid conversation ID'}), 400
    except Exception as e:
        app.logger.error(f"Error deleting conversation: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete conversation'}), 500

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
        
        # Handle free tier access
        if getattr(request, 'access_type', None) == 'free_tier':
            from auth import FreeAccessManager
            free_info = FreeAccessManager.log_free_query(model)
            app.logger.info(f"Free tier chat: model={model}, remaining={free_info['queries_remaining']}")
        
        app.logger.info(f"Chat request: model={model}, message_length={len(user_message)}")
        
        # Get conversation history if conversation exists
        messages = []
        if conversation_id:
            conv_uuid = uuid.UUID(conversation_id)
            conversation = Conversation.query.get_or_404(conv_uuid)
            db_messages = Message.query.filter_by(conversation_id=conv_uuid).order_by(Message.timestamp.asc()).all()
            messages = llm_service.format_conversation_for_llm(db_messages)
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
        # Log prompt details
        app.logger.debug(f"LLM request with {len(messages)} messages for model {model}")
        
        # Add current user message
        messages.append({'role': 'user', 'content': user_message})
        
        # Check if user is authenticated (not free tier)
        is_authenticated = getattr(request, 'access_type', None) != 'free_tier'
        
        app.logger.info(f"Calling LLM service for model: {model}, authenticated: {is_authenticated}")
        # Get AI response and usage info
        ai_response, tokens, estimated_cost = llm_service.get_response(model, messages, is_authenticated=is_authenticated)
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
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Add updated free access info if applicable
        if getattr(request, 'access_type', None) == 'free_tier':
            from auth import FreeAccessManager
            updated_free_info = FreeAccessManager.check_free_access()
            response_data['free_access'] = updated_free_info
        
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Chat error: {str(e)}", exc_info=True)
        # Log error to database
        try:
            from models import LLMErrorLog
            error_log = LLMErrorLog(
                model=model if 'model' in locals() else 'unknown',
                conversation_id=conversation_id if 'conversation_id' in locals() and conversation_id else None,
                error_message=str(e)
            )
            db.session.add(error_log)
            db.session.commit()
        except Exception as db_error:
            app.logger.error(f"Failed to log error to database: {db_error}")
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
        
        # Create context item using new context management system
        try:
            context_item = ContextService.create_context_item(
                name=filename,
                content_type='document',
                content_text=processed_content,
                description=f"Uploaded document - {task_type}",
                original_filename=filename,
                file_size=len(content) if content else 0,
                extra_data={
                    'task_type': task_type,
                    'original_content': content[:1000] if content else None  # Store first 1000 chars of original
                }
            )
            
            # Automatically add context item to current conversation
            ContextService.add_context_to_conversation(
                conversation_id=conversation_id,
                context_item_id=str(context_item.id),
                relevance_score=1.0
            )
            
            app.logger.info(f"Created context item {context_item.id} for conversation {conversation_id}")
            
        except Exception as context_error:
            app.logger.error(f"Failed to create context item: {context_error}")
            # Continue with old system as fallback
        
        # Keep old system for backward compatibility
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
            'filename': filename, 
            'content': processed_content,
            'task_type': task_type,
            'original_content': content  # Keep original for reference
        })
        
        conversation.context_documents = docs
        db.session.commit()
        
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

# ==================== CONTEXT MANAGEMENT API ENDPOINTS ====================

@app.route('/api/context', methods=['GET'])
def get_context_items():
    """Get all context items for current user"""
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        items = ContextService.get_user_context_items(include_inactive=include_inactive)
        
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
                    'original_filename': item.original_filename
                }
                for item in items
            ]
        })
    except Exception as e:
        app.logger.error(f"Error fetching context items: {str(e)}")
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
            content_text=data.get('content_text'),
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
        context = ContextService.get_conversation_context(conversation_id)
        return jsonify({
            'success': True,
            'context': context
        })
    
    except Exception as e:
        app.logger.error(f"Error fetching conversation context: {str(e)}")
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
        stats = ContextService.get_user_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        app.logger.error(f"Error fetching context stats: {str(e)}")
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
    """Get current model settings"""
    try:
        # Check if user is authenticated
        from auth import current_user_id
        user_id = current_user_id()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # For now, return default settings stored in session or file
        # You can enhance this to store in database per user
        settings_file = os.path.join(app.instance_path, 'model_settings.json')
        
        if os.path.exists(settings_file):
            import json
            with open(settings_file, 'r') as f:
                settings = json.load(f)
        else:
            # Default settings - most models enabled except GPT-5
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
        
        return jsonify(settings)
    
    except Exception as e:
        app.logger.error(f"Error getting model settings: {str(e)}")
        return jsonify({'error': 'Failed to get model settings'}), 500

@app.route('/api/model-settings', methods=['POST'])
def save_model_settings():
    """Save model settings"""
    try:
        # Check if user is authenticated
        from auth import current_user_id
        user_id = current_user_id()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        settings = request.get_json()
        if not settings:
            return jsonify({'error': 'No settings provided'}), 400
        
        # Ensure instance path exists
        os.makedirs(app.instance_path, exist_ok=True)
        
        # Save settings to file (you can enhance this to use database)
        settings_file = os.path.join(app.instance_path, 'model_settings.json')
        import json
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
        
        app.logger.info(f"Model settings saved for user {user_id}")
        return jsonify({'success': True, 'message': 'Settings saved successfully'})
    
    except Exception as e:
        app.logger.error(f"Error saving model settings: {str(e)}")
        return jsonify({'error': 'Failed to save model settings'}), 500

@app.route('/api/check-model-access', methods=['POST'])
def check_model_access():
    """Check if a specific model is accessible"""
    try:
        # Check if user is authenticated
        from auth import current_user_id
        user_id = current_user_id()
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        model = data.get('model')
        if not model:
            return jsonify({'error': 'Model not specified'}), 400
        
        # Import LLM service to check model access
        from llm_service import LLMService
        llm_service = LLMService()
        
        # Check if model is accessible by attempting to get info or make a test call
        has_access = False
        try:
            # Try to check model access - this is model-specific logic
            # Use os.getenv() to match how LLM service checks for API keys
            if model.startswith('gpt-') or model.startswith('o1-'):
                # OpenAI models - check if API key is configured
                openai_key = os.getenv('OPENAI_API_KEY')
                has_access = bool(openai_key and openai_key.strip())
                
            elif model.startswith('claude-'):
                # Anthropic models - check if API key is configured
                anthropic_key = os.getenv('ANTHROPIC_API_KEY')
                has_access = bool(anthropic_key and anthropic_key.strip())
                
            elif model.startswith('gemini-'):
                # Google models - check if API key is configured
                google_key = os.getenv('GOOGLE_API_KEY')
                has_access = bool(google_key and google_key.strip())
                
            elif model in ['llama2-70b', 'mixtral-8x7b', 'codellama-34b']:
                # Hugging Face models - check if API key is configured
                hf_key = os.getenv('HUGGINGFACE_API_KEY')
                has_access = bool(hf_key and hf_key.strip())
                
            elif model.startswith('stable-'):
                # Stability AI models - check if API key is configured
                stability_key = os.getenv('STABILITY_API_KEY')
                has_access = bool(stability_key and stability_key.strip())
                
            else:
                # Unknown model
                has_access = False
                
            # For GPT-5 specifically, you might want additional checks
            if model == 'gpt-5':
                # GPT-5 might have special access requirements
                # For now, assume it's not available unless specifically enabled
                has_access = False
                
        except Exception as model_error:
            app.logger.error(f"Error checking model {model} access: {str(model_error)}")
            has_access = False
        
        app.logger.info(f"Model {model} access check: {has_access}")
        return jsonify({
            'success': True,
            'model': model,
            'hasAccess': has_access
        })
    
    except Exception as e:
        app.logger.error(f"Error checking model access: {str(e)}")
        return jsonify({'error': 'Failed to check model access'}), 500

# ==================== END MODEL SETTINGS API ====================

# ==================== ANALYTICS API ====================

@app.route('/api/ip-whitelist', methods=['GET'])
@auth.access_required(allow_free=False)
def api_get_ip_whitelist():
    """Get all IP whitelist entries"""
    try:
        from models import IPWhitelist
        
        # Query all whitelist entries, ordered by creation date
        whitelist_entries = db.session.query(IPWhitelist)\
            .order_by(IPWhitelist.created_at.desc())\
            .all()
        
        # Convert to JSON-serializable format
        result = []
        for entry in whitelist_entries:
            result.append({
                'id': str(entry.id),
                'ip_address': entry.ip_address,
                'description': entry.description,
                'created_at': entry.created_at.isoformat() if entry.created_at else None,
                'created_by': entry.created_by,
                'is_active': entry.is_active
            })
        
        app.logger.info(f"Retrieved {len(result)} IP whitelist entries")
        return jsonify({
            'success': True,
            'data': result,
            'count': len(result)
        })
    
    except Exception as e:
        app.logger.error(f"Error fetching IP whitelist: {str(e)}")
        return jsonify({'error': 'Failed to fetch IP whitelist'}), 500

@app.route('/api/ip-whitelist', methods=['POST'])
@auth.access_required(allow_free=False)
def api_add_ip_whitelist():
    """Add IP address to whitelist"""
    try:
        from models import IPWhitelist
        from auth import current_user_id
        import ipaddress
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        ip_address = data.get('ip_address', '').strip()
        description = data.get('description', '').strip()
        
        if not ip_address:
            return jsonify({'error': 'IP address is required'}), 400
        
        # Validate IP address format
        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            return jsonify({'error': 'Invalid IP address format'}), 400
        
        # Check if IP already exists
        existing = db.session.query(IPWhitelist)\
            .filter(IPWhitelist.ip_address == ip_address)\
            .first()
        
        if existing:
            if existing.is_active:
                return jsonify({'error': 'IP address already whitelisted'}), 409
            else:
                # Reactivate existing entry
                existing.is_active = True
                existing.description = description or existing.description
                existing.created_by = current_user_id()
                db.session.commit()
                
                app.logger.info(f"Reactivated IP whitelist entry: {ip_address}")
                return jsonify({
                    'success': True,
                    'message': 'IP address reactivated in whitelist',
                    'data': {
                        'id': str(existing.id),
                        'ip_address': existing.ip_address,
                        'description': existing.description,
                        'is_active': existing.is_active
                    }
                })
        
        # Create new whitelist entry
        new_entry = IPWhitelist(
            ip_address=ip_address,
            description=description or 'Added via dashboard',
            created_by=current_user_id(),
            is_active=True
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        app.logger.info(f"Added new IP to whitelist: {ip_address}")
        return jsonify({
            'success': True,
            'message': 'IP address added to whitelist successfully',
            'data': {
                'id': str(new_entry.id),
                'ip_address': new_entry.ip_address,
                'description': new_entry.description,
                'is_active': new_entry.is_active
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error adding IP to whitelist: {str(e)}")
        return jsonify({'error': 'Failed to add IP to whitelist'}), 500

@app.route('/api/ip-whitelist/<whitelist_id>', methods=['DELETE'])
@auth.access_required(allow_free=False)
def api_remove_ip_whitelist(whitelist_id):
    """Remove IP address from whitelist (soft delete)"""
    try:
        from models import IPWhitelist
        
        # Find the whitelist entry
        entry = db.session.query(IPWhitelist)\
            .filter(IPWhitelist.id == whitelist_id)\
            .first()
        
        if not entry:
            return jsonify({'error': 'IP whitelist entry not found'}), 404
        
        # Soft delete by setting is_active to False
        entry.is_active = False
        db.session.commit()
        
        app.logger.info(f"Removed IP from whitelist: {entry.ip_address}")
        return jsonify({
            'success': True,
            'message': f'IP address {entry.ip_address} removed from whitelist'
        })
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error removing IP from whitelist: {str(e)}")
        return jsonify({'error': 'Failed to remove IP from whitelist'}), 500

@app.route('/api/ip-whitelist/<whitelist_id>', methods=['PATCH'])
@auth.access_required(allow_free=False)
def api_update_ip_whitelist(whitelist_id):
    """Update IP whitelist entry description"""
    try:
        from models import IPWhitelist
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        entry = db.session.query(IPWhitelist)\
            .filter(IPWhitelist.id == whitelist_id)\
            .first()
        
        if not entry:
            return jsonify({'error': 'IP whitelist entry not found'}), 404
        
        # Update description
        if 'description' in data:
            entry.description = data['description'].strip()
        
        db.session.commit()
        
        app.logger.info(f"Updated IP whitelist entry: {entry.ip_address}")
        return jsonify({
            'success': True,
            'message': 'IP whitelist entry updated successfully',
            'data': {
                'id': str(entry.id),
                'ip_address': entry.ip_address,
                'description': entry.description,
                'is_active': entry.is_active
            }
        })
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating IP whitelist: {str(e)}")
        return jsonify({'error': 'Failed to update IP whitelist entry'}), 500

@app.route('/api/usage-stats', methods=['GET'])
@auth.access_required(allow_free=False)
def api_get_usage_stats():
    """Get LLM usage statistics"""
    try:
        from models import LLMUsageLog
        from datetime import datetime, timedelta
        
        # Get time range parameter (default to 30 days)
        days = request.args.get('days', 30, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Query usage data
        usage_stats = db.session.query(
            LLMUsageLog.model,
            db.func.count(LLMUsageLog.id).label('total_requests'),
            db.func.sum(LLMUsageLog.tokens).label('total_tokens'),
            db.func.avg(LLMUsageLog.tokens).label('avg_tokens'),
            db.func.sum(LLMUsageLog.estimated_cost).label('total_cost')
        ).filter(
            LLMUsageLog.timestamp >= start_date
        ).group_by(
            LLMUsageLog.model
        ).order_by(
            db.func.count(LLMUsageLog.id).desc()
        ).all()
        
        # Convert to JSON format
        stats = []
        total_requests = 0
        total_tokens = 0
        total_cost = 0.0
        
        for stat in usage_stats:
            stat_data = {
                'model': stat.model,
                'requests': int(stat.total_requests),
                'tokens': int(stat.total_tokens or 0),
                'avg_tokens': float(stat.avg_tokens or 0),
                'cost': float(stat.total_cost or 0)
            }
            stats.append(stat_data)
            total_requests += stat_data['requests']
            total_tokens += stat_data['tokens']
            total_cost += stat_data['cost']
        
        # Get recent activity for timeline
        recent_logs = db.session.query(LLMUsageLog)\
            .filter(LLMUsageLog.timestamp >= start_date)\
            .order_by(LLMUsageLog.timestamp.desc())\
            .limit(100)\
            .all()
        
        timeline_data = []
        for log in recent_logs:
            timeline_data.append({
                'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                'model': log.model,
                'tokens': log.tokens,
                'cost': float(log.estimated_cost or 0)
            })
        
        app.logger.info(f"Retrieved usage stats for {days} days: {len(stats)} models, {total_requests} requests")
        
        return jsonify({
            'success': True,
            'data': {
                'stats': stats,
                'timeline': timeline_data,
                'summary': {
                    'total_requests': total_requests,
                    'total_tokens': total_tokens,
                    'total_cost': total_cost,
                    'unique_models': len(stats),
                    'period_days': days
                }
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error fetching usage stats: {str(e)}")
        return jsonify({'error': 'Failed to fetch usage statistics'}), 500

@app.route('/api/activity-log', methods=['GET'])
@auth.access_required(allow_free=False)
def api_get_activity_log():
    """Get system activity log from multiple sources"""
    try:
        from models import LLMUsageLog, LLMErrorLog, FreeAccessLog
        from datetime import datetime, timedelta
        
        # Get time range parameter (default to 7 days)
        days = request.args.get('days', 7, type=int)
        limit = request.args.get('limit', 50, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        activities = []
        
        # Get recent LLM usage activities
        usage_logs = db.session.query(LLMUsageLog)\
            .filter(LLMUsageLog.timestamp >= start_date)\
            .order_by(LLMUsageLog.timestamp.desc())\
            .limit(20)\
            .all()
        
        for log in usage_logs:
            activities.append({
                'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                'type': 'usage',
                'action': f'{log.model} request completed',
                'details': f'{log.tokens} tokens, ${log.estimated_cost:.4f}' if log.tokens and log.estimated_cost else None,
                'status': 'success',
                'model': log.model
            })
        
        # Get recent error activities
        error_logs = db.session.query(LLMErrorLog)\
            .filter(LLMErrorLog.timestamp >= start_date)\
            .order_by(LLMErrorLog.timestamp.desc())\
            .limit(10)\
            .all()
        
        for log in error_logs:
            activities.append({
                'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                'type': 'error',
                'action': f'{log.model} request failed',
                'details': log.error_message[:100] + '...' if len(log.error_message) > 100 else log.error_message,
                'status': 'error',
                'model': log.model
            })
        
        # Get recent access activities
        access_logs = db.session.query(FreeAccessLog)\
            .filter(FreeAccessLog.timestamp >= start_date)\
            .order_by(FreeAccessLog.timestamp.desc())\
            .limit(15)\
            .all()
        
        for log in access_logs:
            activities.append({
                'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                'type': 'access',
                'action': f'Free tier access from {log.ip_address}',
                'details': f'{log.model} model, {log.query_count} queries',
                'status': 'info',
                'ip_address': log.ip_address
            })
        
        # Sort all activities by timestamp (most recent first)
        activities.sort(key=lambda x: x['timestamp'] or '', reverse=True)
        
        # Limit results
        activities = activities[:limit]
        
        app.logger.info(f"Retrieved {len(activities)} activity log entries for {days} days")
        
        return jsonify({
            'success': True,
            'data': activities,
            'count': len(activities),
            'period_days': days
        })
    
    except Exception as e:
        app.logger.error(f"Error fetching activity log: {str(e)}")
        return jsonify({'error': 'Failed to fetch activity log'}), 500

@app.route('/api/activity-log', methods=['DELETE'])
@auth.access_required(allow_free=False)
def api_clear_activity_log():
    """Clear activity logs (for demo purposes - careful in production!)"""
    try:
        # Note: This is a dangerous operation in production
        # Consider implementing soft delete or archiving instead
        
        # For safety, let's just return success without actually deleting
        # In a real implementation, you might archive old logs instead
        
        app.logger.warning("Activity log clear requested - not implemented for safety")
        
        return jsonify({
            'success': True,
            'message': 'Activity log cleared (simulated - actual logs preserved for audit)',
            'note': 'In production, consider implementing log archiving instead of deletion'
        })
    
    except Exception as e:
        app.logger.error(f"Error clearing activity log: {str(e)}")
        return jsonify({'error': 'Failed to clear activity log'}), 500

# ==================== END ANALYTICS API ====================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)