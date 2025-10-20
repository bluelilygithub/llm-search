"""
Error Handlers for Flask Application
Provides structured error handling and user-friendly error responses
"""

from flask import jsonify, request, current_app
from functools import wraps
from marshmallow import ValidationError
import traceback
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APIException(Exception):
    """Custom API Exception for structured error handling"""
    
    def __init__(self, message, status_code=500, payload=None, error_code=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}
        self.error_code = error_code or 'INTERNAL_ERROR'
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self):
        """Convert exception to dictionary for JSON response"""
        result = {
            'error': self.error_code,
            'message': self.message,
            'timestamp': self.timestamp
        }
        
        if self.payload:
            result.update(self.payload)
            
        return result

def handle_api_errors(f):
    """
    Decorator to handle API errors consistently
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        
        except ValidationError as e:
            logger.warning(f"Validation error in {f.__name__}: {e.messages}")
            return jsonify({
                'error': 'VALIDATION_ERROR',
                'message': 'The provided data is invalid',
                'validation_errors': e.messages,
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        except APIException as e:
            logger.error(f"API exception in {f.__name__}: {e.message}")
            return jsonify(e.to_dict()), e.status_code
        
        except FileNotFoundError as e:
            logger.error(f"File not found in {f.__name__}: {str(e)}")
            return jsonify({
                'error': 'NOT_FOUND',
                'message': 'The requested resource was not found',
                'timestamp': datetime.utcnow().isoformat()
            }), 404
        
        except PermissionError as e:
            logger.error(f"Permission error in {f.__name__}: {str(e)}")
            return jsonify({
                'error': 'PERMISSION_DENIED',
                'message': 'You do not have permission to perform this action',
                'timestamp': datetime.utcnow().isoformat()
            }), 403
        
        except ValueError as e:
            logger.error(f"Value error in {f.__name__}: {str(e)}")
            return jsonify({
                'error': 'INVALID_INPUT',
                'message': 'Invalid input provided',
                'details': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        except Exception as e:
            # Log the full traceback for debugging
            logger.error(f"Unexpected error in {f.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Don't expose internal error details in production
            if current_app.config.get('DEBUG', False):
                return jsonify({
                    'error': 'INTERNAL_ERROR',
                    'message': 'An internal server error occurred',
                    'details': str(e),
                    'traceback': traceback.format_exc(),
                    'timestamp': datetime.utcnow().isoformat()
                }), 500
            else:
                return jsonify({
                    'error': 'INTERNAL_ERROR',
                    'message': 'An internal server error occurred. Please try again later.',
                    'timestamp': datetime.utcnow().isoformat()
                }), 500
    
    return decorated_function

def validate_json_request(schema):
    """
    Decorator to validate JSON request data against a schema
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                raise APIException(
                    'Request must be JSON',
                    status_code=400,
                    error_code='INVALID_CONTENT_TYPE'
                )
            
            try:
                validated_data = schema.load(request.get_json())
                # Pass validated data to the endpoint
                return f(validated_data, *args, **kwargs)
            except ValidationError as e:
                raise APIException(
                    'Validation failed',
                    status_code=400,
                    error_code='VALIDATION_ERROR',
                    payload={'validation_errors': e.messages}
                )
        
        return decorated_function
    return decorator

def require_uuid(param_name):
    """
    Decorator to validate UUID parameters
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            import uuid
            param_value = kwargs.get(param_name)
            
            if not param_value:
                raise APIException(
                    f'Missing required parameter: {param_name}',
                    status_code=400,
                    error_code='MISSING_PARAMETER'
                )
            
            try:
                # Validate UUID format
                uuid.UUID(param_value)
            except (ValueError, TypeError):
                raise APIException(
                    f'Invalid UUID format for parameter: {param_name}',
                    status_code=400,
                    error_code='INVALID_UUID'
                )
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def log_api_request(f):
    """
    Decorator to log API requests for monitoring
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = datetime.utcnow()
        
        # Log request
        logger.info(f"API Request: {request.method} {request.path} from {request.remote_addr}")
        
        try:
            result = f(*args, **kwargs)
            
            # Log successful response
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"API Response: {request.method} {request.path} - Success ({duration:.3f}s)")
            
            return result
        
        except Exception as e:
            # Log error response
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"API Response: {request.method} {request.path} - Error: {str(e)} ({duration:.3f}s)")
            raise
    
    return decorated_function

def rate_limit_exceeded_handler(e):
    """
    Handler for rate limit exceeded errors
    """
    return jsonify({
        'error': 'RATE_LIMIT_EXCEEDED',
        'message': 'Too many requests. Please try again later.',
        'retry_after': e.retry_after,
        'timestamp': datetime.utcnow().isoformat()
    }), 429

def csrf_error_handler(e):
    """
    Handler for CSRF errors
    """
    return jsonify({
        'error': 'CSRF_ERROR',
        'message': 'CSRF token missing or invalid',
        'timestamp': datetime.utcnow().isoformat()
    }), 400

def not_found_handler(e):
    """
    Handler for 404 errors
    """
    return jsonify({
        'error': 'NOT_FOUND',
        'message': 'The requested resource was not found',
        'timestamp': datetime.utcnow().isoformat()
    }), 404

def method_not_allowed_handler(e):
    """
    Handler for 405 errors
    """
    return jsonify({
        'error': 'METHOD_NOT_ALLOWED',
        'message': f'Method {request.method} not allowed for this endpoint',
        'allowed_methods': list(e.valid_methods),
        'timestamp': datetime.utcnow().isoformat()
    }), 405

def register_error_handlers(app):
    """
    Register all error handlers with the Flask app
    """
    app.errorhandler(404)(not_found_handler)
    app.errorhandler(405)(method_not_allowed_handler)
    
    # Register rate limiting handler if flask-limiter is being used
    try:
        from flask_limiter import RateLimitExceeded
        app.errorhandler(RateLimitExceeded)(rate_limit_exceeded_handler)
    except ImportError:
        pass
    
    # Register CSRF handler if flask-wtf is being used
    try:
        from flask_wtf.csrf import CSRFError
        app.errorhandler(CSRFError)(csrf_error_handler)
    except ImportError:
        pass

# Common API Exceptions for easy use
class ValidationException(APIException):
    def __init__(self, message, validation_errors=None):
        super().__init__(
            message=message,
            status_code=400,
            error_code='VALIDATION_ERROR',
            payload={'validation_errors': validation_errors} if validation_errors else None
        )

class NotFoundException(APIException):
    def __init__(self, resource_type="Resource"):
        super().__init__(
            message=f'{resource_type} not found',
            status_code=404,
            error_code='NOT_FOUND'
        )

class UnauthorizedException(APIException):
    def __init__(self, message="Authentication required"):
        super().__init__(
            message=message,
            status_code=401,
            error_code='UNAUTHORIZED'
        )

class ForbiddenException(APIException):
    def __init__(self, message="Access denied"):
        super().__init__(
            message=message,
            status_code=403,
            error_code='FORBIDDEN'
        )

class ConflictException(APIException):
    def __init__(self, message="Resource conflict"):
        super().__init__(
            message=message,
            status_code=409,
            error_code='CONFLICT'
        )

class RateLimitException(APIException):
    def __init__(self, message="Rate limit exceeded", retry_after=60):
        super().__init__(
            message=message,
            status_code=429,
            error_code='RATE_LIMIT_EXCEEDED',
            payload={'retry_after': retry_after}
        )
