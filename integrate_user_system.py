"""
Integration Script for Multi-User System
Updates main app.py to integrate with the new user management system
"""

def create_app_integration():
    """
    Create the integration code to add to app.py
    This includes importing the new modules and registering blueprints
    """
    
    integration_code = '''
# ==================== MULTI-USER SYSTEM INTEGRATION ====================

# Import user management modules
try:
    from user_models import User, Organization, UserSession, UserAuditLog, UserRole, UserStatus
    from auth_service import auth_service, AuthenticationError, AuthorizationError
    from user_api import user_bp
    
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
    @app.route('/migrate-user-system', methods=['GET', 'POST'])
    def migrate_user_system_endpoint():
        """Web endpoint to migrate to multi-user system"""
        try:
            from migrate_user_system import migrate_to_multi_user_system
            
            if request.method == 'GET':
                return render_template('migration_info.html')
            
            # Run migration
            result = migrate_to_multi_user_system()
            
            return jsonify(result), 200
            
        except Exception as e:
            app.logger.error(f"User system migration failed: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Migration failed: {str(e)}'
            }), 500
    
    # Enhanced authentication check for existing endpoints
    def require_user_auth(f):
        """Enhanced authentication decorator"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = auth_service.get_current_user()
            if not user:
                # Fallback to old auth system for backward compatibility
                from auth import auth
                has_access, access_type, free_info = auth.has_access()
                if not has_access:
                    return jsonify({'error': 'Authentication required'}), 401
                
                # Set legacy user info
                g.legacy_access = True
                g.access_type = access_type
                g.free_info = free_info
            else:
                g.legacy_access = False
                g.current_user = user
            
            return f(*args, **kwargs)
        return decorated_function
    
    # Update existing security utils to work with new user system
    def get_current_user_identity():
        """Get current user identity (new or legacy system)"""
        if hasattr(g, 'current_user') and g.current_user:
            # New user system
            return {
                'type': 'authenticated',
                'user_id': str(g.current_user.id),
                'username': g.current_user.username,
                'role': g.current_user.role.value,
                'organization_id': str(g.current_user.organization_id) if g.current_user.organization_id else None
            }
        else:
            # Fallback to legacy system
            from security_utils import get_user_identity
            return get_user_identity()
    
    app.logger.info("Multi-user system integration loaded successfully")
    
except ImportError as e:
    app.logger.warning(f"Multi-user system not available: {str(e)}")
    app.logger.info("Falling back to legacy authentication system")

# ==================== END MULTI-USER SYSTEM INTEGRATION ====================
'''
    
    return integration_code

def create_migration_template():
    """Create a template for the migration info page"""
    
    template_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-User System Migration</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .warning {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }
        .success {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }
        .btn {
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        .btn:hover {
            background-color: #0056b3;
        }
        .btn-danger {
            background-color: #dc3545;
        }
        .btn-danger:hover {
            background-color: #c82333;
        }
        .feature-list {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 4px;
            margin: 20px 0;
        }
        .feature-list ul {
            margin: 0;
            padding-left: 20px;
        }
        .feature-list li {
            margin: 5px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Multi-User System Migration</h1>
        
        <p>This migration will upgrade your AI Knowledge Base from a single-user system to a comprehensive multi-user platform with advanced authentication, roles, and permissions.</p>
        
        <div class="feature-list">
            <h3>✨ New Features You'll Get:</h3>
            <ul>
                <li><strong>User Registration & Login</strong> - Proper user accounts with secure authentication</li>
                <li><strong>Role-Based Access Control</strong> - Super Admin, Admin, User, Viewer, and Guest roles</li>
                <li><strong>Organization Management</strong> - Multi-tenant support for teams and companies</li>
                <li><strong>Session Management</strong> - Secure session handling with activity tracking</li>
                <li><strong>Audit Logging</strong> - Complete audit trail of all user actions</li>
                <li><strong>Password Reset</strong> - Secure password reset via email</li>
                <li><strong>Email Verification</strong> - Email verification for new accounts</li>
                <li><strong>API Key Management</strong> - Personal API keys for each user</li>
                <li><strong>Enhanced Security</strong> - Modern security practices and protections</li>
            </ul>
        </div>
        
        <div class="warning">
            <h4>⚠️ Important Notes:</h4>
            <ul>
                <li>This migration will modify your database structure</li>
                <li>All existing data will be preserved and assigned to a default admin user</li>
                <li>The default admin credentials will be: <strong>admin / admin123</strong></li>
                <li><strong>You MUST change the admin password immediately after migration</strong></li>
                <li>Make sure to backup your database before proceeding</li>
            </ul>
        </div>
        
        <div style="margin: 30px 0;">
            <h3>Migration Steps:</h3>
            <ol>
                <li>Creates new user management tables (users, organizations, sessions, audit_logs)</li>
                <li>Creates a default organization called "Default Organization"</li>
                <li>Creates a default admin user with super admin privileges</li>
                <li>Adds user_id columns to existing tables (conversations, projects, context_items)</li>
                <li>Assigns all existing data to the default admin user</li>
                <li>Sets up proper foreign key relationships</li>
            </ol>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <button class="btn" onclick="runMigration()">🚀 Run Migration</button>
        </div>
        
        <div id="result" style="margin-top: 20px;"></div>
    </div>
    
    <script>
        async function runMigration() {
            const resultDiv = document.getElementById('result');
            const btn = document.querySelector('.btn');
            
            btn.disabled = true;
            btn.textContent = '⏳ Running Migration...';
            
            try {
                const response = await fetch('/migrate-user-system', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });
                
                const result = await response.json();
                
                if (result.success) {
                    resultDiv.innerHTML = `
                        <div class="success">
                            <h4>✅ Migration Successful!</h4>
                            <p>${result.message}</p>
                            <ul>
                                <li>Conversations updated: ${result.stats.conversations_updated}</li>
                                <li>Projects updated: ${result.stats.projects_updated}</li>
                                <li>Context items updated: ${result.stats.context_items_updated}</li>
                                <li>Admin User ID: ${result.stats.admin_user_id}</li>
                                <li>Organization ID: ${result.stats.organization_id}</li>
                            </ul>
                            <p><strong>Default Admin Credentials:</strong></p>
                            <p>Username: <code>admin</code><br>Password: <code>admin123</code></p>
                            <p><strong>⚠️ Please change the admin password immediately!</strong></p>
                        </div>
                    `;
                } else {
                    resultDiv.innerHTML = `
                        <div class="warning">
                            <h4>❌ Migration Failed</h4>
                            <p>Error: ${result.error}</p>
                        </div>
                    `;
                }
            } catch (error) {
                resultDiv.innerHTML = `
                    <div class="warning">
                        <h4>❌ Migration Failed</h4>
                        <p>Error: ${error.message}</p>
                    </div>
                `;
            }
            
            btn.disabled = false;
            btn.textContent = '🚀 Run Migration';
        }
    </script>
</body>
</html>'''
    
    return template_content

if __name__ == '__main__':
    print("Multi-User System Integration Code:")
    print("=" * 50)
    print(create_app_integration())
    print("\n\nMigration Template:")
    print("=" * 50)
    print(create_migration_template())
