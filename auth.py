from functools import wraps
from flask import session, redirect, url_for, request, jsonify
import os
import hashlib
import secrets

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
            return jsonify({
                'authenticated': self.is_authenticated(),
                'auth_enabled': self.is_auth_enabled()
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

# Create global auth instance
auth = SimpleAuth()

def require_auth(f):
    """Convenience decorator for requiring authentication"""
    return auth.login_required(f)