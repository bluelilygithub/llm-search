from functools import wraps
from flask import session, redirect, url_for, request, jsonify
import os
import hashlib
import secrets
from datetime import datetime, timedelta
import uuid

class FreeAccessManager:
    """Manage free tier access with 10 queries per 24 hours"""
    
    FREE_QUERY_LIMIT = 10
    RESET_HOURS = 24
    
    @classmethod
    def get_session_id(cls):
        """Get or create session ID for free access tracking"""
        if 'free_session_id' not in session:
            session['free_session_id'] = str(uuid.uuid4())
        return session['free_session_id']
    
    @classmethod
    def check_free_access(cls, session_id=None):
        """Check if user has free queries remaining"""
        from database import db
        from models import FreeAccessLog
        
        if session_id is None:
            session_id = cls.get_session_id()
        
        # Get queries in the last 24 hours for this session
        cutoff_time = datetime.utcnow() - timedelta(hours=cls.RESET_HOURS)
        
        query_count = db.session.query(
            db.func.coalesce(db.func.sum(FreeAccessLog.query_count), 0)
        ).filter(
            FreeAccessLog.session_id == session_id,
            FreeAccessLog.timestamp >= cutoff_time
        ).scalar()
        
        remaining = max(0, cls.FREE_QUERY_LIMIT - query_count)
        
        return {
            'has_access': remaining > 0,
            'queries_used': query_count,
            'queries_remaining': remaining,
            'limit': cls.FREE_QUERY_LIMIT,
            'reset_time': cutoff_time + timedelta(hours=cls.RESET_HOURS)
        }
    
    @classmethod
    def log_free_query(cls, model, session_id=None):
        """Log a free tier query"""
        from database import db
        from models import FreeAccessLog
        
        if session_id is None:
            session_id = cls.get_session_id()
        
        # Log the query
        log_entry = FreeAccessLog(
            session_id=session_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:500],  # Truncate
            model=model,
            query_count=1
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
        return cls.check_free_access(session_id)

class SimpleAuth:
    """Simple authentication system for demo/development use"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize authentication with Flask app"""
        # Set secure session configuration
        app.config['SESSION_COOKIE_SECURE'] = not app.debug
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        
        # Register auth routes
        self.register_routes(app)
    
    def register_routes(self, app):
        """Register authentication routes"""
        
        @app.route('/auth/status')
        def auth_status():
            """Check authentication status"""
            auth_enabled = self.is_auth_enabled()
            authenticated = self.is_authenticated()
            
            # If not authenticated but auth is enabled, check free access
            free_access_info = None
            if auth_enabled and not authenticated:
                free_access_info = FreeAccessManager.check_free_access()
            
            return jsonify({
                'authenticated': authenticated,
                'auth_enabled': auth_enabled,
                'free_access': free_access_info
            })
        
        @app.route('/auth/login', methods=['POST'])
        def login():
            """Simple login endpoint"""
            if not self.is_auth_enabled():
                return jsonify({'success': True, 'message': 'Authentication disabled'})
            
            data = request.get_json()
            password = data.get('password', '')
            
            if self.verify_password(password):
                session['authenticated'] = True
                session['user_id'] = 'admin'  # Simple single-user system
                return jsonify({'success': True, 'message': 'Login successful'})
            else:
                return jsonify({'success': False, 'error': 'Invalid password'}), 401
        
        @app.route('/auth/logout', methods=['POST'])
        def logout():
            """Logout endpoint"""
            session.pop('authenticated', None)
            session.pop('user_id', None)
            return jsonify({'success': True, 'message': 'Logged out'})
    
    def is_auth_enabled(self):
        """Check if authentication is enabled"""
        return bool(os.getenv('AUTH_PASSWORD'))
    
    def is_authenticated(self):
        """Check if user is authenticated"""
        if not self.is_auth_enabled():
            return True  # No auth required
        return session.get('authenticated', False)
    
    def has_access(self, require_query=False):
        """Check if user has access (authenticated OR free tier)"""
        if self.is_authenticated():
            return True, 'authenticated', None
        
        if not self.is_auth_enabled():
            return True, 'no_auth', None
        
        # Check free access
        free_access = FreeAccessManager.check_free_access()
        if free_access['has_access']:
            return True, 'free_tier', free_access
        
        return False, 'no_access', free_access
    
    def verify_password(self, password):
        """Verify password against stored hash"""
        stored_password = os.getenv('AUTH_PASSWORD')
        if not stored_password:
            return True  # No password set
        
        # Simple password comparison for demo
        # In production, use proper password hashing (bcrypt, scrypt, etc.)
        return password == stored_password
    
    def login_required(self, f):
        """Decorator to require authentication"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not self.is_authenticated():
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                else:
                    return redirect(url_for('login_page'))
            return f(*args, **kwargs)
        return decorated_function
    
    def access_required(self, allow_free=False):
        """Decorator to require access (auth or free tier)"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                has_access, access_type, free_info = self.has_access()
                
                if not has_access:
                    if request.is_json:
                        return jsonify({
                            'error': 'Access denied',
                            'free_access': free_info
                        }), 403
                    else:
                        return redirect(url_for('login_page'))
                
                # For free tier access on query endpoints, log the usage
                if access_type == 'free_tier' and allow_free and 'chat' in request.endpoint:
                    # This will be handled in the chat endpoint
                    pass
                
                # Add access info to the request context
                request.access_type = access_type
                request.free_info = free_info
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator

# Create global auth instance
auth = SimpleAuth()

def require_auth(f):
    """Convenience decorator for requiring authentication"""
    return auth.login_required(f)