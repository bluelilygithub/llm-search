from app import app, db
from models import Conversation, Message, Attachment, SearchQuery, Project
from sqlalchemy import text

def init_database():
    """Initialize the database with required extensions and tables."""
    with app.app_context():
        try:
            # Enable pgvector extension
            db.session.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
            db.session.commit()
            
            # Create all tables
            db.create_all()
            
            print("Database initialized successfully!")
            return True
        except Exception as e:
            print(f"Database initialization failed: {e}")
            return False

def test_connection():
    """Test database connection."""
    with app.app_context():
        try:
            db.session.execute(text('SELECT 1'))
            print("Database connection successful!")
            return True
        except Exception as e:
            print(f"Database connection failed: {e}")
            return False

if __name__ == '__main__':
    if test_connection():
        init_database()