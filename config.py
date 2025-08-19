import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Database connection pooling
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.getenv('DB_POOL_SIZE', '10')),
        'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', '30')),
        'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '3600')),  # 1 hour
        'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '20')),
        'pool_pre_ping': True,  # Validate connections before use
    }
    
    # Embedding configuration
    EMBEDDING_MODEL = 'text-embedding-3-small'
    EMBEDDING_DIMENSION = 1536
    
    # Search configuration
    DEFAULT_SEARCH_LIMIT = 10
    MAX_SEARCH_LIMIT = 50
    
    # Production optimizations
    SQLALCHEMY_RECORD_QUERIES = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    @staticmethod
    def init_app(app):
        """Initialize app-specific configuration"""
        pass

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_timeout': 30,
        'pool_recycle': 3600,
        'max_overflow': 10,
        'pool_pre_ping': True,
    }

class ProductionConfig(Config):
    DEBUG = False
    # Use larger connection pool for production
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_timeout': 30,
        'pool_recycle': 1800,  # 30 minutes
        'max_overflow': 50,
        'pool_pre_ping': True,
    }
    
    @staticmethod
    def init_app(app):
        """Production-specific initialization"""
        Config.init_app(app)
        
        # Log to stderr in production
        import logging
        from logging import StreamHandler
        file_handler = StreamHandler()
        file_handler.setLevel(logging.WARNING)
        app.logger.addHandler(file_handler)

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL', 'sqlite:///:memory:')
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 2,
        'pool_timeout': 10,
        'pool_recycle': 3600,
        'max_overflow': 5,
        'pool_pre_ping': True,
    }

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}