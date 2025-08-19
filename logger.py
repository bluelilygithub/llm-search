import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logging(app):
    """Configure logging for the application"""
    
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Configure logging level based on environment
    log_level = logging.DEBUG if app.debug else logging.INFO
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s:%(lineno)d: %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s'
    )
    
    # Configure root logger
    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s: %(message)s')
    
    # File handler for all logs
    file_handler = RotatingFileHandler(
        'logs/app.log', 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(detailed_formatter)
    
    # Error file handler
    error_handler = RotatingFileHandler(
        'logs/error.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    
    # Add handlers to app logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(error_handler)
    app.logger.setLevel(log_level)
    
    # Configure specific loggers
    configure_service_loggers()
    
    app.logger.info("Logging configured successfully")

def configure_service_loggers():
    """Configure loggers for specific services"""
    
    # LLM Service logger
    llm_logger = logging.getLogger('llm_service')
    llm_logger.setLevel(logging.INFO)
    
    # Database logger
    db_logger = logging.getLogger('database')
    db_logger.setLevel(logging.INFO)
    
    # Disable werkzeug logs in production
    if not os.getenv('FLASK_DEBUG'):
        logging.getLogger('werkzeug').setLevel(logging.WARNING)

def get_logger(name):
    """Get a configured logger instance"""
    return logging.getLogger(name)