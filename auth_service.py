"""
Enhanced Authentication Service
Comprehensive user authentication with session management, permissions, and security features
"""

from flask import session, request, current_app, g
from functools import wraps
from datetime import datetime, timedelta
import secrets
import logging
from user_models import User, UserSession, UserAuditLog, UserRole, UserStatus
from database import db

logger = logging.getLogger(__name__)

class AuthenticationError(Exception):
    """Custom authentication exception"""
    pass

class AuthorizationError(Exception):
    """Custom authorization exception"""
    pass

class AuthService:
    """Enhanced authentication service with comprehensive user management"""
    
    def __init__(self):
        self.session_timeout = timedelta(hours=24)  # Default session timeout
        self.max_sessions_per_user = 5  # Maximum concurrent sessions
    
    def register_user(self, username, email, password, **kwargs):
        """Register a new user with validation"""
        try:
            # Validate input
            if not username or len(username) < 3:
                raise ValueError("Username must be at least 3 characters long")
            
            if not email or '@' not in email:
                raise ValueError("Valid email address is required")
            
            if not password or len(password) < 8:
                raise ValueError("Password must be at least 8 characters long")
            
            # Check if user already exists
            existing_user = User.query.filter(
                (User.username == username) | (User.email == email.lower())
            ).first()
            
            if existing_user:
                if existing_user.username == username:
                    raise ValueError("Username already exists")
                else:
                    raise ValueError("Email already registered")
            
            # Create new user
            user = User(
                username=username,
                email=email,
                password=password,
                **kwargs
            )
            
            # Generate email verification token
            user.generate_email_verification_token()
            
            # Set default role based on organization
            if kwargs.get('organization_id'):
                user.role = UserRole.USER
            else:
                # First user becomes super admin
                if User.query.count() == 0:
                    user.role = UserRole.SUPER_ADMIN
                else:
                    user.role = UserRole.USER
            
            db.session.add(user)
            db.session.commit()
            
            # Log registration
            self._log_user_action(
                user_id=user.id,
                action='user_registered',
                success=True,
                details={'username': username, 'email': email}
            )
            
            logger.info(f"User registered successfully: {username} ({email})")
            return user
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"User registration failed: {str(e)}")
            raise
    
    def authenticate_user(self, username_or_email, password, remember_me=False):
        """Authenticate user and create session"""
        try:
            # Find user by username or email
            user = User.query.filter(
                (User.username == username_or_email) | 
                (User.email == username_or_email.lower())
            ).first()
            
            if not user:
                self._log_user_action(
                    action='login_failed',
                    success=False,
                    details={'username_or_email': username_or_email, 'reason': 'user_not_found'}
                )
                raise AuthenticationError("Invalid username/email or password")
            
            # Check password
            if not user.check_password(password):
                self._log_user_action(
                    user_id=user.id,
                    action='login_failed',
                    success=False,
                    details={'reason': 'invalid_password'}
                )
                raise AuthenticationError("Invalid username/email or password")
            
            # Check user status
            if user.status != UserStatus.ACTIVE:
                self._log_user_action(
                    user_id=user.id,
                    action='login_failed',
                    success=False,
                    details={'reason': 'account_inactive', 'status': user.status.value}
                )
                raise AuthenticationError(f"Account is {user.status.value}")
            
            # Create session
            session_token = self._create_user_session(user, remember_me)
            
            # Update user login info
            user.last_login_at = datetime.utcnow()
            user.login_count += 1
            user.update_activity()
            
            db.session.commit()
            
            # Log successful login
            self._log_user_action(
                user_id=user.id,
                action='login_success',
                success=True,
                details={'session_token': session_token[:8] + '...'}
            )
            
            logger.info(f"User authenticated successfully: {user.username}")
            return user, session_token
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Authentication failed: {str(e)}")
            raise
    
    def _create_user_session(self, user, remember_me=False):
        """Create a new user session"""
        # Clean up old sessions if user has too many
        active_sessions = UserSession.query.filter_by(
            user_id=user.id,
            is_active=True
        ).order_by(UserSession.last_activity_at.desc()).all()
        
        if len(active_sessions) >= self.max_sessions_per_user:
            # Deactivate oldest sessions
            for old_session in active_sessions[self.max_sessions_per_user-1:]:
                old_session.is_active = False
        
        # Create new session
        session_duration = timedelta(days=30) if remember_me else self.session_timeout
        
        user_session = UserSession(
            user_id=user.id,
            session_token=secrets.token_urlsafe(32),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            expires_at=datetime.utcnow() + session_duration
        )
        
        db.session.add(user_session)
        
        # Set Flask session
        session['user_id'] = str(user.id)
        session['session_token'] = user_session.session_token
        session.permanent = remember_me
        
        return user_session.session_token
    
    def get_current_user(self):
        """Get currently authenticated user"""
        if hasattr(g, 'current_user'):
            return g.current_user
        
        user_id = session.get('user_id')
        session_token = session.get('session_token')
        
        if not user_id or not session_token:
            return None
        
        # Validate session
        user_session = UserSession.query.filter_by(
            session_token=session_token,
            is_active=True
        ).first()
        
        if not user_session or user_session.expires_at < datetime.utcnow():
            self.logout_user()
            return None
        
        # Get user
        user = User.query.get(user_id)
        if not user or user.status != UserStatus.ACTIVE:
            self.logout_user()
            return None
        
        # Update session activity
        user_session.last_activity_at = datetime.utcnow()
        user.update_activity()
        
        # Cache in request context
        g.current_user = user
        return user
    
    def logout_user(self, session_token=None):
        """Logout user and invalidate session"""
        try:
            current_user = self.get_current_user()
            
            # Get session token
            if not session_token:
                session_token = session.get('session_token')
            
            if session_token:
                # Invalidate session in database
                user_session = UserSession.query.filter_by(
                    session_token=session_token
                ).first()
                
                if user_session:
                    user_session.is_active = False
                    db.session.commit()
            
            # Clear Flask session
            session.clear()
            
            # Clear request context
            if hasattr(g, 'current_user'):
                delattr(g, 'current_user')
            
            # Log logout
            if current_user:
                self._log_user_action(
                    user_id=current_user.id,
                    action='logout',
                    success=True
                )
                logger.info(f"User logged out: {current_user.username}")
            
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
    
    def require_auth(self, f):
        """Decorator to require authentication"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = self.get_current_user()
            if not user:
                raise AuthenticationError("Authentication required")
            return f(*args, **kwargs)
        return decorated_function
    
    def require_role(self, *required_roles):
        """Decorator to require specific roles"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                user = self.get_current_user()
                if not user:
                    raise AuthenticationError("Authentication required")
                
                if user.role not in required_roles:
                    raise AuthorizationError(f"Role {user.role.value} not authorized")
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    def require_permission(self, permission):
        """Decorator to require specific permission"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                user = self.get_current_user()
                if not user:
                    raise AuthenticationError("Authentication required")
                
                if not user.has_permission(permission):
                    raise AuthorizationError(f"Permission '{permission}' required")
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    def verify_email(self, token):
        """Verify user email with token"""
        user = User.query.filter_by(email_verification_token=token).first()
        
        if not user:
            raise ValueError("Invalid verification token")
        
        user.email_verified = True
        user.email_verification_token = None
        
        if user.status == UserStatus.PENDING_VERIFICATION:
            user.status = UserStatus.ACTIVE
        
        db.session.commit()
        
        self._log_user_action(
            user_id=user.id,
            action='email_verified',
            success=True
        )
        
        return user
    
    def request_password_reset(self, email):
        """Request password reset for user"""
        user = User.query.filter_by(email=email.lower()).first()
        
        if not user:
            # Don't reveal if email exists
            logger.warning(f"Password reset requested for non-existent email: {email}")
            return None
        
        # Generate reset token
        reset_token = user.generate_password_reset_token()
        db.session.commit()
        
        self._log_user_action(
            user_id=user.id,
            action='password_reset_requested',
            success=True
        )
        
        return reset_token
    
    def reset_password(self, token, new_password):
        """Reset user password with token"""
        user = User.query.filter(
            User.password_reset_token == token,
            User.password_reset_expires > datetime.utcnow()
        ).first()
        
        if not user:
            raise ValueError("Invalid or expired reset token")
        
        # Update password
        user.set_password(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        
        # Invalidate all sessions
        UserSession.query.filter_by(user_id=user.id).update({'is_active': False})
        
        db.session.commit()
        
        self._log_user_action(
            user_id=user.id,
            action='password_reset_completed',
            success=True
        )
        
        return user
    
    def _log_user_action(self, action, success=True, user_id=None, details=None):
        """Log user action for audit trail"""
        try:
            audit_log = UserAuditLog(
                user_id=user_id,
                action=action,
                ip_address=request.remote_addr if request else None,
                user_agent=request.headers.get('User-Agent', '') if request else None,
                success=success,
                details=details or {}
            )
            
            db.session.add(audit_log)
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Failed to log user action: {str(e)}")
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions (run periodically)"""
        try:
            expired_count = UserSession.query.filter(
                UserSession.expires_at < datetime.utcnow()
            ).update({'is_active': False})
            
            db.session.commit()
            
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired sessions")
            
            return expired_count
            
        except Exception as e:
            logger.error(f"Session cleanup failed: {str(e)}")
            return 0

# Global auth service instance
auth_service = AuthService()
