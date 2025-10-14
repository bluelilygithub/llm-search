"""
Migration script to add project template fields to existing projects table.
Run this once to update your database schema.
"""

from app import app, db
from models import Project
from sqlalchemy import text

def migrate_project_template_fields():
    """Add new template fields to the projects table"""
    
    with app.app_context():
        try:
            print("Starting migration: Adding project template fields...")
            
            # List of new columns to add
            new_columns = [
                "agent_name VARCHAR(255)",
                "agent_role VARCHAR(500)",
                "agent_personality VARCHAR(500)",
                "primary_goal TEXT",
                "goal_steps TEXT",
                "rules_do TEXT",
                "rules_dont TEXT",
                "context_background TEXT",
                "user_role VARCHAR(500)",
                "output_format TEXT"
            ]
            
            # Check which columns already exist
            existing_columns = []
            try:
                result = db.session.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'projects'
                """))
                existing_columns = [row[0] for row in result]
                print(f"Existing columns: {existing_columns}")
            except Exception as e:
                print(f"Could not check existing columns: {e}")
            
            # Add each column if it doesn't exist
            for column_def in new_columns:
                column_name = column_def.split()[0]
                
                if column_name not in existing_columns:
                    try:
                        alter_sql = f"ALTER TABLE projects ADD COLUMN {column_def}"
                        print(f"Adding column: {column_name}")
                        db.session.execute(text(alter_sql))
                        db.session.commit()
                        print(f"✓ Added column: {column_name}")
                    except Exception as e:
                        print(f"✗ Failed to add column {column_name}: {e}")
                        db.session.rollback()
                else:
                    print(f"○ Column {column_name} already exists, skipping")
            
            print("Migration completed successfully!")
            return True
            
        except Exception as e:
            print(f"Migration failed: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    success = migrate_project_template_fields()
    if success:
        print("✓ Database migration completed successfully!")
        print("You can now use the project template features.")
    else:
        print("✗ Migration failed. Please check the errors above.")
