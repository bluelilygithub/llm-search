"""
Database Migration Script for Multi-User System
Migrates existing single-user data to multi-user architecture
"""

from database import db
from models import Conversation, Message, Project, ContextItem
from user_models import User, Organization, UserRole, UserStatus
from sqlalchemy import text
import uuid
import logging

logger = logging.getLogger(__name__)

def migrate_to_multi_user_system():
    """
    Migrate existing data to multi-user system
    This script should be run once to transition from single-user to multi-user
    """
    try:
        logger.info("Starting migration to multi-user system...")
        
        # Step 1: Create new tables
        logger.info("Creating new user management tables...")
        try:
            db.create_all()
            logger.info("Tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {str(e)}")
            raise
        
        # Step 2: Create default organization
        logger.info("Creating default organization...")
        try:
            default_org = Organization.query.filter_by(slug='default').first()
            if not default_org:
                logger.info("Organization not found, creating new one...")
                default_org = Organization(
                    name='Default Organization',
                    slug='default',
                    description='Default organization for migrated users'
                )
                db.session.add(default_org)
                db.session.flush()
                logger.info(f"Organization created with ID: {default_org.id}")
            else:
                logger.info(f"Organization already exists with ID: {default_org.id}")
        except Exception as e:
            logger.error(f"Error creating organization: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
        
        # Step 3: Create default admin user
        logger.info("Creating default admin user...")
        try:
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                logger.info("Admin user not found, creating new one...")
                # Create admin user with required args, then set optional fields
                admin_user = User(
                    username='admin',
                    email='admin@example.com',
                    password='admin123',  # Should be changed immediately
                )
                logger.info("User object created, setting additional fields...")
                # Set additional fields after initialization
                admin_user.first_name = 'System'
                admin_user.last_name = 'Administrator'
                admin_user.role = UserRole.SUPER_ADMIN
                admin_user.status = UserStatus.ACTIVE
                admin_user.email_verified = True
                admin_user.organization_id = default_org.id
                
                logger.info("Adding user to session...")
                db.session.add(admin_user)
                db.session.flush()
                logger.info(f"Admin user created with ID: {admin_user.id}")
            else:
                logger.info(f"Admin user already exists with ID: {admin_user.id}")
        except Exception as e:
            logger.error(f"Error creating admin user: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
        
        # Step 4: Add user_id columns to existing tables if they don't exist
        logger.info("Adding user_id columns to existing tables...")
        
        # Check if columns exist and add them if needed
        tables_to_update = [
            ('conversations', 'user_id'),
            ('projects', 'user_id'),
            ('context_items', 'user_id')
        ]
        
        for table_name, column_name in tables_to_update:
            try:
                # Check if column exists
                result = db.session.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}' 
                    AND column_name = '{column_name}'
                """)).fetchone()
                
                if not result:
                    # Add the column
                    logger.info(f"Adding {column_name} to {table_name}")
                    db.session.execute(text(f"""
                        ALTER TABLE {table_name} 
                        ADD COLUMN {column_name} UUID
                    """))
                    
                    # Add foreign key constraint
                    db.session.execute(text(f"""
                        ALTER TABLE {table_name}
                        ADD CONSTRAINT fk_{table_name}_{column_name}
                        FOREIGN KEY ({column_name}) REFERENCES users(id)
                    """))
                    
                    db.session.commit()
                    logger.info(f"Successfully added {column_name} to {table_name}")
                else:
                    logger.info(f"Column {column_name} already exists in {table_name}")
                    
            except Exception as e:
                logger.warning(f"Could not add {column_name} to {table_name}: {str(e)}")
                db.session.rollback()
        
        # Step 5: Migrate existing data to default user
        logger.info("Migrating existing data to default admin user...")
        
        # Update conversations
        conversations_updated = db.session.execute(text("""
            UPDATE conversations 
            SET user_id = :user_id 
            WHERE user_id IS NULL
        """), {'user_id': str(admin_user.id)}).rowcount
        
        # Update projects
        projects_updated = db.session.execute(text("""
            UPDATE projects 
            SET user_id = :user_id 
            WHERE user_id IS NULL
        """), {'user_id': str(admin_user.id)}).rowcount
        
        # Update context items
        context_items_updated = db.session.execute(text("""
            UPDATE context_items 
            SET user_id = :user_id 
            WHERE user_id IS NULL
        """), {'user_id': str(admin_user.id)}).rowcount
        
        db.session.commit()
        
        logger.info(f"Migration completed successfully!")
        logger.info(f"- Updated {conversations_updated} conversations")
        logger.info(f"- Updated {projects_updated} projects") 
        logger.info(f"- Updated {context_items_updated} context items")
        logger.info(f"- Created admin user: {admin_user.username}")
        logger.info(f"- Default admin password: admin123 (CHANGE IMMEDIATELY)")
        
        return {
            'success': True,
            'message': 'Migration completed successfully',
            'stats': {
                'conversations_updated': conversations_updated,
                'projects_updated': projects_updated,
                'context_items_updated': context_items_updated,
                'admin_user_id': str(admin_user.id),
                'organization_id': str(default_org.id)
            }
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Migration failed: {str(e)}")
        raise

def rollback_migration():
    """
    Rollback migration (removes user system)
    WARNING: This will delete all user data!
    """
    try:
        logger.warning("Starting migration rollback...")
        logger.warning("This will delete all user management data!")
        
        # Drop user management tables
        tables_to_drop = [
            'user_audit_logs',
            'user_sessions', 
            'users',
            'organizations'
        ]
        
        for table in tables_to_drop:
            try:
                db.session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                logger.info(f"Dropped table: {table}")
            except Exception as e:
                logger.warning(f"Could not drop table {table}: {str(e)}")
        
        # Remove user_id columns from existing tables
        tables_to_update = [
            ('conversations', 'user_id'),
            ('projects', 'user_id'),
            ('context_items', 'user_id')
        ]
        
        for table_name, column_name in tables_to_update:
            try:
                db.session.execute(text(f"""
                    ALTER TABLE {table_name} 
                    DROP COLUMN IF EXISTS {column_name}
                """))
                logger.info(f"Removed {column_name} from {table_name}")
            except Exception as e:
                logger.warning(f"Could not remove {column_name} from {table_name}: {str(e)}")
        
        db.session.commit()
        logger.info("Migration rollback completed")
        
        return {'success': True, 'message': 'Migration rollback completed'}
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Rollback failed: {str(e)}")
        raise

if __name__ == '__main__':
    # Run migration
    result = migrate_to_multi_user_system()
    print(f"Migration result: {result}")
