"""Security utilities for access control and validation"""

from functools import wraps
from flask import jsonify, session, request, current_app
from models import Conversation, Message, Project, ContextItem
from auth import SimpleAuth
import uuid
import logging
import hashlib

security_logger = logging.getLogger('security')

def get_user_identity():
    """Get current user identity (authenticated or session-based)"""
    from auth import FreeAccessManager
    auth = SimpleAuth()
    
    if auth.is_authenticated():
        # Authenticated user - use a consistent identifier based on IP + auth status
        # This ensures authenticated users can see their conversations across sessions
        ip = FreeAccessManager.get_client_ip()
        user_id = f"auth_{hashlib.sha256(ip.encode()).hexdigest()[:16]}"
        
        return {
            'type': 'authenticated',
            'user_id': user_id,
            'session_id': None
        }
    else:
        # Free/anonymous user - use session-based identification
        session_id = request.cookies.get('session_id')
        if not session_id:
            # Check Flask session as fallback
            session_id = session.get('free_session_id')
        
        return {
            'type': 'free',
            'user_id': None,
            'session_id': session_id
        }

def validate_uuid(uuid_string):
    """Validate UUID format"""
    try:
        uuid.UUID(uuid_string)
        return True
    except (ValueError, TypeError):
        return False

def check_conversation_access(conversation_id, user_identity=None):
    """Check if user has access to conversation"""
    if not validate_uuid(conversation_id):
        return False, "Invalid conversation ID format"
    
    if not user_identity:
        user_identity = get_user_identity()
    
    try:
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return False, "Conversation not found"
        
        # Check ownership based on user type
        if user_identity['type'] == 'authenticated':
            # Authenticated users check user_id
            if conversation.user_id == user_identity['user_id']:
                return True, "Access granted"
        else:
            # Free users check session_id
            if conversation.session_id == user_identity['session_id']:
                return True, "Access granted"
        
        # Log unauthorized access attempt
        security_logger.warning(
            f"Unauthorized conversation access attempt: "
            f"conversation_id={conversation_id}, "
            f"user_identity={user_identity['type']}, "
            f"ip={request.remote_addr}"
        )
        
        return False, "Access denied"
        
    except Exception as e:
        security_logger.error(f"Error checking conversation access: {e}")
        return False, "Access check failed"

def check_message_access(message_id, user_identity=None):
    """Check if user has access to message (via conversation ownership)"""
    if not validate_uuid(message_id):
        return False, "Invalid message ID format"
    
    try:
        message = Message.query.get(message_id)
        if not message:
            return False, "Message not found"
        
        # Check access via conversation
        return check_conversation_access(str(message.conversation_id), user_identity)
        
    except Exception as e:
        security_logger.error(f"Error checking message access: {e}")
        return False, "Access check failed"

def check_project_access(project_id, user_identity=None):
    """Check if user has access to project"""
    if not validate_uuid(project_id):
        return False, "Invalid project ID format"
    
    if not user_identity:
        user_identity = get_user_identity()
    
    try:
        project = Project.query.get(project_id)
        if not project:
            return False, "Project not found"
        
        # For now, projects are user-specific based on conversations
        # Check if user has any conversations in this project
        conversations = Conversation.query.filter_by(project_id=project_id).all()
        
        for conv in conversations:
            has_access, _ = check_conversation_access(str(conv.id), user_identity)
            if has_access:
                return True, "Access granted"
        
        return False, "Access denied"
        
    except Exception as e:
        security_logger.error(f"Error checking project access: {e}")
        return False, "Access check failed"

def check_context_item_access(context_item_id, user_identity=None):
    """Check if user has access to context item"""
    if not validate_uuid(context_item_id):
        return False, "Invalid context item ID format"
    
    if not user_identity:
        user_identity = get_user_identity()
    
    try:
        context_item = ContextItem.query.get(context_item_id)
        if not context_item:
            return False, "Context item not found"
        
        # Context items are user-specific
        if user_identity['type'] == 'authenticated':
            if context_item.user_id == user_identity['user_id']:
                return True, "Access granted"
        else:
            # For free users, check session-based ownership
            from context_service import ContextService
            current_user_id = ContextService.get_user_id()
            if context_item.user_id == current_user_id:
                return True, "Access granted"
        
        return False, "Access denied"
        
    except Exception as e:
        security_logger.error(f"Error checking context item access: {e}")
        return False, "Access check failed"

def require_conversation_access(f):
    """Decorator to require conversation access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        conversation_id = kwargs.get('conversation_id') or kwargs.get('id')
        if not conversation_id:
            return jsonify({'error': 'Conversation ID required'}), 400
        
        has_access, message = check_conversation_access(conversation_id)
        if not has_access:
            return jsonify({'error': message}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def require_message_access(f):
    """Decorator to require message access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        message_id = kwargs.get('message_id') or kwargs.get('id')
        if not message_id:
            return jsonify({'error': 'Message ID required'}), 400
        
        has_access, message = check_message_access(message_id)
        if not has_access:
            return jsonify({'error': message}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def require_project_access(f):
    """Decorator to require project access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        project_id = kwargs.get('project_id') or kwargs.get('id')
        if not project_id:
            return jsonify({'error': 'Project ID required'}), 400
        
        has_access, message = check_project_access(project_id)
        if not has_access:
            return jsonify({'error': message}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def require_context_item_access(f):
    """Decorator to require context item access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        context_item_id = kwargs.get('item_id') or kwargs.get('context_item_id')
        if not context_item_id:
            return jsonify({'error': 'Context item ID required'}), 400
        
        has_access, message = check_context_item_access(context_item_id)
        if not has_access:
            return jsonify({'error': message}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def sanitize_filename(filename):
    """Sanitize filename to prevent path traversal"""
    import re
    import os
    
    if not filename:
        return "unnamed_file"
    
    # Remove path components
    filename = os.path.basename(filename)
    
    # Remove dangerous characters
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Prevent hidden files
    if filename.startswith('.'):
        filename = '_' + filename[1:]
    
    # Prevent empty filename
    if not filename or filename == '.':
        filename = "unnamed_file"
    
    return filename