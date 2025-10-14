"""
User Management API Endpoints
Comprehensive REST API for user registration, authentication, and management
"""

from flask import Blueprint, request, jsonify, session
from auth_service import auth_service, AuthenticationError, AuthorizationError
from user_models import User, UserRole, UserStatus, Organization
from database import db
import logging

logger = logging.getLogger(__name__)

# Create Blueprint for user management
user_bp = Blueprint('user_api', __name__, url_prefix='/api/users')

@user_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Extract required fields
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        # Optional fields
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        organization_name = data.get('organization_name', '').strip()
        
        # Validate required fields
        if not username:
            return jsonify({'error': 'Username is required'}), 400
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        if not password:
            return jsonify({'error': 'Password is required'}), 400
        
        # Create organization if provided
        organization_id = None
        if organization_name:
            # Check if organization exists
            org = Organization.query.filter_by(name=organization_name).first()
            if not org:
                # Create new organization
                org_slug = organization_name.lower().replace(' ', '-').replace('_', '-')
                org = Organization(
                    name=organization_name,
                    slug=org_slug
                )
                db.session.add(org)
                db.session.flush()  # Get the ID
            
            organization_id = org.id
        
        # Register user
        user = auth_service.register_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            organization_id=organization_id
        )
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'user': user.to_dict(),
            'email_verification_required': not user.email_verified
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@user_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and create session"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        username_or_email = data.get('username_or_email', '').strip()
        password = data.get('password', '')
        remember_me = data.get('remember_me', False)
        
        if not username_or_email or not password:
            return jsonify({'error': 'Username/email and password are required'}), 400
        
        # Authenticate user
        user, session_token = auth_service.authenticate_user(
            username_or_email=username_or_email,
            password=password,
            remember_me=remember_me
        )
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': user.to_dict(),
            'session_token': session_token
        }), 200
        
    except AuthenticationError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@user_bp.route('/logout', methods=['POST'])
def logout():
    """Logout current user"""
    try:
        auth_service.logout_user()
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500

@user_bp.route('/me', methods=['GET'])
@auth_service.require_auth
def get_current_user():
    """Get current user profile"""
    try:
        user = auth_service.get_current_user()
        
        return jsonify({
            'success': True,
            'user': user.to_dict(include_sensitive=True)
        }), 200
        
    except Exception as e:
        logger.error(f"Get current user error: {str(e)}")
        return jsonify({'error': 'Failed to get user profile'}), 500

@user_bp.route('/me', methods=['PUT'])
@auth_service.require_auth
def update_profile():
    """Update current user profile"""
    try:
        user = auth_service.get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update allowed fields
        allowed_fields = [
            'first_name', 'last_name', 'display_name', 'avatar_url',
            'timezone', 'language', 'preferences'
        ]
        
        for field in allowed_fields:
            if field in data:
                setattr(user, field, data[field])
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'user': user.to_dict(include_sensitive=True)
        }), 200
        
    except Exception as e:
        logger.error(f"Update profile error: {str(e)}")
        return jsonify({'error': 'Failed to update profile'}), 500

@user_bp.route('/change-password', methods=['POST'])
@auth_service.require_auth
def change_password():
    """Change user password"""
    try:
        user = auth_service.get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        
        if not current_password or not new_password:
            return jsonify({'error': 'Current and new passwords are required'}), 400
        
        # Verify current password
        if not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        # Validate new password
        if len(new_password) < 8:
            return jsonify({'error': 'New password must be at least 8 characters long'}), 400
        
        # Update password
        user.set_password(new_password)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Change password error: {str(e)}")
        return jsonify({'error': 'Failed to change password'}), 500

@user_bp.route('/verify-email/<token>', methods=['POST'])
def verify_email(token):
    """Verify user email with token"""
    try:
        user = auth_service.verify_email(token)
        
        return jsonify({
            'success': True,
            'message': 'Email verified successfully',
            'user': user.to_dict()
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        return jsonify({'error': 'Email verification failed'}), 500

@user_bp.route('/request-password-reset', methods=['POST'])
def request_password_reset():
    """Request password reset"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email', '').strip()
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # Request password reset (always return success for security)
        auth_service.request_password_reset(email)
        
        return jsonify({
            'success': True,
            'message': 'If the email exists, a password reset link has been sent'
        }), 200
        
    except Exception as e:
        logger.error(f"Password reset request error: {str(e)}")
        return jsonify({'error': 'Failed to process password reset request'}), 500

@user_bp.route('/reset-password/<token>', methods=['POST'])
def reset_password(token):
    """Reset password with token"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        new_password = data.get('new_password', '')
        
        if not new_password:
            return jsonify({'error': 'New password is required'}), 400
        
        if len(new_password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400
        
        # Reset password
        user = auth_service.reset_password(token, new_password)
        
        return jsonify({
            'success': True,
            'message': 'Password reset successfully'
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        return jsonify({'error': 'Password reset failed'}), 500

# Admin endpoints
@user_bp.route('/', methods=['GET'])
@auth_service.require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)
def list_users():
    """List all users (admin only)"""
    try:
        current_user = auth_service.get_current_user()
        
        # Build query
        query = User.query
        
        # Filter by organization for regular admins
        if current_user.role == UserRole.ADMIN and current_user.organization_id:
            query = query.filter_by(organization_id=current_user.organization_id)
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Filters
        role = request.args.get('role')
        status = request.args.get('status')
        search = request.args.get('search', '').strip()
        
        if role:
            query = query.filter_by(role=UserRole(role))
        
        if status:
            query = query.filter_by(status=UserStatus(status))
        
        if search:
            query = query.filter(
                (User.username.ilike(f'%{search}%')) |
                (User.email.ilike(f'%{search}%')) |
                (User.first_name.ilike(f'%{search}%')) |
                (User.last_name.ilike(f'%{search}%'))
            )
        
        # Execute query
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        users = [user.to_dict() for user in pagination.items]
        
        return jsonify({
            'success': True,
            'users': users,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        }), 200
        
    except Exception as e:
        logger.error(f"List users error: {str(e)}")
        return jsonify({'error': 'Failed to list users'}), 500

@user_bp.route('/<user_id>', methods=['GET'])
@auth_service.require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)
def get_user(user_id):
    """Get specific user (admin only)"""
    try:
        current_user = auth_service.get_current_user()
        
        user = User.query.get_or_404(user_id)
        
        # Check access permissions
        if (current_user.role == UserRole.ADMIN and 
            current_user.organization_id != user.organization_id):
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify({
            'success': True,
            'user': user.to_dict(include_sensitive=True)
        }), 200
        
    except Exception as e:
        logger.error(f"Get user error: {str(e)}")
        return jsonify({'error': 'Failed to get user'}), 500

@user_bp.route('/<user_id>/status', methods=['PUT'])
@auth_service.require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)
def update_user_status(user_id):
    """Update user status (admin only)"""
    try:
        current_user = auth_service.get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        user = User.query.get_or_404(user_id)
        
        # Check access permissions
        if (current_user.role == UserRole.ADMIN and 
            current_user.organization_id != user.organization_id):
            return jsonify({'error': 'Access denied'}), 403
        
        # Prevent self-modification
        if user.id == current_user.id:
            return jsonify({'error': 'Cannot modify your own status'}), 400
        
        new_status = data.get('status')
        if not new_status:
            return jsonify({'error': 'Status is required'}), 400
        
        try:
            user.status = UserStatus(new_status)
        except ValueError:
            return jsonify({'error': 'Invalid status'}), 400
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'User status updated successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Update user status error: {str(e)}")
        return jsonify({'error': 'Failed to update user status'}), 500

# Error handlers
@user_bp.errorhandler(AuthenticationError)
def handle_auth_error(e):
    return jsonify({'error': str(e)}), 401

@user_bp.errorhandler(AuthorizationError)
def handle_authz_error(e):
    return jsonify({'error': str(e)}), 403
