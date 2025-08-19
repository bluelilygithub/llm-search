image.pngimport os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Embedding configuration
    EMBEDDING_MODEL = 'text-embedding-3-small'
    EMBEDDING_DIMENSION = 1536
    
    # Search configuration
    DEFAULT_SEARCH_LIMIT = 10
    MAX_SEARCH_LIMIT = 50