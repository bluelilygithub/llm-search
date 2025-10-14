"""
User Management Models
Comprehensive multi-user system with roles and permissions
"""

from database import db
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import UUID
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import enum
import secrets

class UserRole(enum.Enum):
    """User roles with hierarchical permissions"""
    SUPER_ADMIN = "super_admin"  # Full system access
    ADMIN = "admin"              # Organization management
    USER = "user"                # Standard user access
    VIEWER = "viewer"            # Read-only access
    GUEST = "guest"              # Limited trial access

class UserStatus(enum.Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"

class User(db.Model):
    """Enhanced User model with comprehensive authentication and profile management"""
    __tablename__ = 'users'
    
    # Primary identification
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    
    # Authentication
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Profile information
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    display_name = db.Column(db.String(100), nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True)
    
    # Role and permissions
    role = db.Column(db.Enum(UserRole), default=UserRole.USER, nullable=False)
    status = db.Column(db.Enum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    permissions = db.Column(db.JSON, default=lambda: [])  # Additional custom permissions
    
    # Organization/team management
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=True)
    
    # Account management
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verification_token = db.Column(db.String(255), nullable=True)
    password_reset_token = db.Column(db.String(255), nullable=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)
    
    # Activity tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_activity_at = db.Column(db.DateTime, nullable=True)
    login_count = db.Column(db.Integer, default=0, nullable=False)
    
    # Security settings
    two_factor_enabled = db.Column(db.Boolean, default=False, nullable=False)
    two_factor_secret = db.Column(db.String(32), nullable=True)
    
    # Preferences
    preferences = db.Column(db.JSON, default=lambda: {})  # User settings and preferences
    timezone = db.Column(db.String(50), default='UTC')
    language = db.Column(db.String(10), default='en')
    
    # Usage tracking
    api_key = db.Column(db.String(64), unique=True, nullable=True, index=True)
    api_calls_count = db.Column(db.Integer, default=0, nullable=False)
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_user_email_status', 'email', 'status'),
        db.Index('idx_user_role_status', 'role', 'status'),
        db.Index('idx_user_last_activity', 'last_activity_at'),
    )
    
    def __init__(self, username, email, password, **kwargs):
        self.username = username
        self.email = email.lower()
        self.set_password(password)
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def set_password(self, password):
        """Set password with secure hashing"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)
    
    def generate_api_key(self):
        """Generate unique API key for user"""
        self.api_key = secrets.token_urlsafe(32)
        return self.api_key
    
    def generate_password_reset_token(self):
        """Generate password reset token"""
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_expires = datetime.utcnow() + timedelta(hours=24)
        return self.password_reset_token
    
    def generate_email_verification_token(self):
        """Generate email verification token"""
        self.email_verification_token = secrets.token_urlsafe(32)
        return self.email_verification_token
    
    def has_permission(self, permission):
        """Check if user has specific permission"""
        # Role-based permissions
        role_permissions = {
            UserRole.SUPER_ADMIN: ['*'],  # All permissions
            UserRole.ADMIN: [
                'manage_users', 'manage_organization', 'view_analytics',
                'manage_projects', 'manage_conversations', 'manage_context'
            ],
            UserRole.USER: [
                'create_conversations', 'manage_own_projects', 'manage_own_context',
                'view_own_analytics'
            ],
            UserRole.VIEWER: [
                'view_conversations', 'view_projects', 'view_context'
            ],
            UserRole.GUEST: [
                'create_conversations'  # Limited access
            ]
        }
        
        # Check role permissions
        user_permissions = role_permissions.get(self.role, [])
        if '*' in user_permissions or permission in user_permissions:
            return True
        
        # Check custom permissions
        return permission in (self.permissions or [])
    
    def can_access_resource(self, resource, action='read'):
        """Check if user can access a specific resource"""
        # Super admin can access everything
        if self.role == UserRole.SUPER_ADMIN:
            return True
        
        # Resource-specific access control
        if hasattr(resource, 'user_id'):
            # User owns the resource
            if str(resource.user_id) == str(self.id):
                return True
        
        if hasattr(resource, 'organization_id') and self.organization_id:
            # Same organization access for admins
            if (resource.organization_id == self.organization_id and 
                self.role in [UserRole.ADMIN]):
                return True
        
        return False
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity_at = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary for API responses"""
        data = {
            'id': str(self.id),
            'username': self.username,
            'email': self.email if include_sensitive else None,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'display_name': self.display_name or f"{self.first_name or ''} {self.last_name or ''}".strip() or self.username,
            'avatar_url': self.avatar_url,
            'role': self.role.value,
            'status': self.status.value,
            'email_verified': self.email_verified,
            'created_at': self.created_at.isoformat(),
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'last_activity_at': self.last_activity_at.isoformat() if self.last_activity_at else None,
            'timezone': self.timezone,
            'language': self.language,
            'two_factor_enabled': self.two_factor_enabled,
            'organization_id': str(self.organization_id) if self.organization_id else None
        }
        
        if include_sensitive:
            data.update({
                'api_key': self.api_key,
                'api_calls_count': self.api_calls_count,
                'login_count': self.login_count,
                'permissions': self.permissions,
                'preferences': self.preferences
            })
        
        return data

class Organization(db.Model):
    """Organization/Company model for multi-tenant support"""
    __tablename__ = 'organizations'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    
    # Settings
    logo_url = db.Column(db.String(500))
    website = db.Column(db.String(255))
    
    # Billing and limits
    plan = db.Column(db.String(50), default='free')  # free, pro, enterprise
    max_users = db.Column(db.Integer, default=5)
    
    # Status
    status = db.Column(db.String(20), default='active')  # active, suspended, trial
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', backref='organization', lazy=True)

class UserSession(db.Model):
    """User session tracking for security and analytics"""
    __tablename__ = 'user_sessions'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    
    # Session details
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='sessions')
    
    # Indexes
    __table_args__ = (
        db.Index('idx_session_user_active', 'user_id', 'is_active'),
        db.Index('idx_session_expires', 'expires_at'),
    )

class UserAuditLog(db.Model):
    """Comprehensive audit logging for user actions"""
    __tablename__ = 'user_audit_logs'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=True)
    
    # Action details
    action = db.Column(db.String(100), nullable=False, index=True)  # login, logout, create_project, etc.
    resource_type = db.Column(db.String(50), nullable=True)  # conversation, project, user, etc.
    resource_id = db.Column(db.String(100), nullable=True)
    
    # Context
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    details = db.Column(db.JSON, nullable=True)  # Additional action-specific data
    
    # Result
    success = db.Column(db.Boolean, default=True, nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = db.relationship('User', backref='audit_logs')
    
    # Indexes for efficient querying
    __table_args__ = (
        db.Index('idx_audit_user_action', 'user_id', 'action'),
        db.Index('idx_audit_resource', 'resource_type', 'resource_id'),
        db.Index('idx_audit_created', 'created_at'),
    )
