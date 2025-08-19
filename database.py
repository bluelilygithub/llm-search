from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import text
import logging

# Create the SQLAlchemy instance
db = SQLAlchemy()
migrate = Migrate()

def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)
    migrate.init_app(app, db)
    return db

def init_database(app):
    """Initialize the database with required extensions and tables."""
    logger = logging.getLogger('database')
    with app.app_context():
        try:
            # Enable pgvector extension
            db.session.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
            db.session.commit()
            
            # Create all tables
            db.create_all()
            
            logger.info("Database initialized successfully!")
            return True
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False

def test_connection(app):
    """Test database connection."""
    logger = logging.getLogger('database')
    with app.app_context():
        try:
            db.session.execute(text('SELECT 1'))
            logger.info("Database connection successful!")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False