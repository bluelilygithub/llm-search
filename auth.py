from functools import wraps
from flask import session, redirect, url_for, request, jsonify
import os
import hashlib
import secrets
from datetime import datetime, timedelta, date
import uuid
import ipaddress

class FreeAccessManager:
    """Robust free tier access management with IP tracking and whitelisting"""
    
    FREE_QUERY_LIMIT = 10
    RESET_HOURS = 24
    
    @classmethod
    def get_client_ip(cls):
        """Get the real client IP, handling proxies/load balancers"""
        # Check for forwarded IP (Railway, Cloudflare, etc.)
        if request.headers.get('CF-Connecting-IP'):
            return request.headers.get('CF-Connecting-IP')
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        if request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        return request.remote_addr
    
    @classmethod
    def get_tracking_key(cls, ip=None):
        """Generate tracking key from IP + User Agent hash"""
        if ip is None:
            ip = cls.get_client_ip()
        user_agent = request.headers.get('User-Agent', '')[:200]
        
        # Create hash of IP + shortened user agent
        combined = f"{ip}:{user_agent}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]
    
    @classmethod 
    def is_whitelisted(cls, ip=None):
        """Check if IP is whitelisted for unlimited access"""
        from database import db
        from models import IPWhitelist
        
        if ip is None:
            ip = cls.get_client_ip()
            
        whitelist_entry = db.session.query(IPWhitelist).filter(
            IPWhitelist.ip_address == ip,
            IPWhitelist.is_active == True
        ).first()
        
        return whitelist_entry is not None, whitelist_entry
    
    @classmethod
    def get_session_id(cls):
        """Get or create session ID for free access tracking"""
        if 'free_session_id' not in session:
            session['free_session_id'] = str(uuid.uuid4())
        return session['free_session_id']
    
    @classmethod
    def check_free_access(cls, session_id=None):
        """Check if user has free queries remaining using hybrid tracking"""
        from database import db
        from models import FreeAccessLog
        
        ip = cls.get_client_ip()
        
        # Check if IP is whitelisted
        is_whitelisted, whitelist_entry = cls.is_whitelisted(ip)
        if is_whitelisted:
            return {
                'has_access': True,
                'queries_used': 0,
                'queries_remaining': 999,
                'limit': 999,
                'reset_time': (datetime.utcnow() + timedelta(hours=24)).isoformat(),
                'reset_time_formatted': 'Unlimited (Whitelisted)',
                'hours_until_reset': 24,
                'whitelisted': True,
                'whitelist_description': whitelist_entry.description if whitelist_entry else 'Unlimited Demo Access'
            }
        
        if session_id is None:
            session_id = cls.get_session_id()
        
        tracking_key = cls.get_tracking_key(ip)
        cutoff_time = datetime.utcnow() - timedelta(hours=cls.RESET_HOURS)
        
        # Check usage by multiple methods and take the maximum
        
        # 1. Session-based usage
        session_usage = db.session.query(
            db.func.coalesce(db.func.sum(FreeAccessLog.query_count), 0)
        ).filter(
            FreeAccessLog.session_id == session_id,
            FreeAccessLog.timestamp >= cutoff_time
        ).scalar()
        
        # 2. IP-based usage
        ip_usage = db.session.query(
            db.func.coalesce(db.func.sum(FreeAccessLog.query_count), 0)
        ).filter(
            FreeAccessLog.ip_address == ip,
            FreeAccessLog.timestamp >= cutoff_time
        ).scalar()
        
        # 3. Tracking key usage (IP + User Agent hash)
        tracking_usage = db.session.query(
            db.func.coalesce(db.func.sum(FreeAccessLog.query_count), 0)
        ).filter(
            FreeAccessLog.tracking_key == tracking_key,
            FreeAccessLog.timestamp >= cutoff_time
        ).scalar()
        
        # Use the highest usage count (most restrictive)
        max_usage = max(session_usage, ip_usage, tracking_usage)
        remaining = max(0, cls.FREE_QUERY_LIMIT - max_usage)
        
        reset_time = cutoff_time + timedelta(hours=cls.RESET_HOURS)
        
        return {
            'has_access': remaining > 0,
            'queries_used': max_usage,
            'queries_remaining': remaining,
            'limit': cls.FREE_QUERY_LIMIT,
            'reset_time': reset_time.isoformat(),
            'reset_time_formatted': reset_time.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'hours_until_reset': max(0, (reset_time - datetime.utcnow()).total_seconds() / 3600),
            'whitelisted': False,
            'tracking_method': f'session:{session_usage}, ip:{ip_usage}, key:{tracking_usage}, max:{max_usage}'
        }
    
    @classmethod
    def log_free_query(cls, model, session_id=None):
        """Log a free tier query with comprehensive tracking"""
        from database import db
        from models import FreeAccessLog, IPUsageSummary
        
        ip = cls.get_client_ip()
        
        # Skip logging if whitelisted
        is_whitelisted, _ = cls.is_whitelisted(ip)
        if is_whitelisted:
            return cls.check_free_access(session_id)
        
        if session_id is None:
            session_id = cls.get_session_id()
        
        tracking_key = cls.get_tracking_key(ip)
        user_agent = request.headers.get('User-Agent', '')[:500]
        
        # Log the query
        log_entry = FreeAccessLog(
            session_id=session_id,
            ip_address=ip,
            user_agent=user_agent,
            model=model,
            query_count=1,
            tracking_key=tracking_key
        )
        
        db.session.add(log_entry)
        
        # Update daily IP usage summary
        today = date.today()
        usage_summary = db.session.query(IPUsageSummary).filter(
            IPUsageSummary.ip_address == ip,
            IPUsageSummary.date == today
        ).first()
        
        if usage_summary:
            usage_summary.total_queries += 1
            usage_summary.last_user_agent = user_agent
            usage_summary.last_activity = datetime.utcnow()
        else:
            usage_summary = IPUsageSummary(
                ip_address=ip,
                date=today,
                total_queries=1,
                unique_sessions=1,
                last_user_agent=user_agent
            )
            db.session.add(usage_summary)
        
        db.session.commit()
        
        return cls.check_free_access(session_id)
    
    @classmethod
    def add_to_whitelist(cls, ip_address, description="Demo Access", created_by="admin"):
        """Add IP to whitelist"""
        from database import db
        from models import IPWhitelist
        
        try:
            # Validate IP address
            ipaddress.ip_address(ip_address)
            
            # Check if already exists
            existing = db.session.query(IPWhitelist).filter(
                IPWhitelist.ip_address == ip_address
            ).first()
            
            if existing:
                existing.is_active = True
                existing.description = description
                existing.created_by = created_by
            else:
                whitelist_entry = IPWhitelist(
                    ip_address=ip_address,
                    description=description,
                    created_by=created_by
                )
                db.session.add(whitelist_entry)
            
            db.session.commit()
            return True, "IP added to whitelist successfully"
            
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def remove_from_whitelist(cls, ip_address):
        """Remove IP from whitelist"""
        from database import db
        from models import IPWhitelist
        
        whitelist_entry = db.session.query(IPWhitelist).filter(
            IPWhitelist.ip_address == ip_address
        ).first()
        
        if whitelist_entry:
            whitelist_entry.is_active = False
            db.session.commit()
            return True, "IP removed from whitelist"
        
        return False, "IP not found in whitelist"

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
        
        # Logout route is now handled in app.py with CSRF exemption
    
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
        
        # Check if stored password is already hashed (starts with known hash prefixes)
        if stored_password.startswith(('$2b$', '$2a$', '$2y$', 'pbkdf2:', 'scrypt:')):
            # Already hashed - use secure verification
            from werkzeug.security import check_password_hash
            return check_password_hash(stored_password, password)
        else:
            # Legacy plaintext password - hash it and update
            from werkzeug.security import generate_password_hash, check_password_hash
            
            # For backward compatibility, check plaintext first
            if password == stored_password:
                # Log warning about plaintext password
                import logging
                logging.getLogger('auth').warning(
                    "SECURITY WARNING: Using plaintext password. "
                    "Please hash your AUTH_PASSWORD using generate_password_hash()"
                )
                return True
            return False
    
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
                        error_msg = 'Access denied'
                        if free_info:
                            hours = int(free_info.get('hours_until_reset', 0))
                            minutes = int((free_info.get('hours_until_reset', 0) % 1) * 60)
                            if hours > 0:
                                error_msg = f'Daily free queries exhausted. Access will reset in {hours}h {minutes}m.'
                            else:
                                error_msg = f'Daily free queries exhausted. Access will reset in {minutes}m.'
                        
                        return jsonify({
                            'error': error_msg,
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

def current_user_id():
    """Get the current user ID if authenticated"""
    if auth.is_authenticated():
        return session.get('user_id', 'admin')  # Default to 'admin' for simple auth
    return None