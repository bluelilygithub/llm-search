"""
Input Validation Schemas for Flask Backend
Provides server-side validation for all API endpoints
"""

from marshmallow import Schema, fields, validate, ValidationError, post_load
import re
import uuid as uuid_lib

class UUIDField(fields.Field):
    """Custom UUID field for validation"""
    
    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        return str(value)
    
    def _deserialize(self, value, attr, data, **kwargs):
        if not value:
            return None
        try:
            return str(uuid_lib.UUID(value))
        except (ValueError, TypeError):
            raise ValidationError('Invalid UUID format')

class ChatMessageSchema(Schema):
    """Schema for chat message validation"""
    message = fields.Str(
        required=True,
        validate=[
            validate.Length(min=1, max=10000, error="Message must be between 1 and 10,000 characters"),
        ]
    )
    model = fields.Str(
        required=True,
        validate=validate.OneOf([
            'gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini',
            'o1-preview', 'o1-mini',
            'claude-3.5-sonnet', 'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku',
            'gemini-pro', 'gemini-flash',
            'llama2-70b', 'mixtral-8x7b', 'codellama-34b'
        ], error="Invalid model selection")
    )
    conversation_id = UUIDField(allow_none=True)
    project_id = UUIDField(allow_none=True)
    
    @post_load
    def sanitize_message(self, data, **kwargs):
        """Sanitize the message content"""
        if 'message' in data:
            # Basic HTML sanitization
            data['message'] = html.escape(data['message'].strip())
        return data

class ProjectSchema(Schema):
    """Schema for project validation"""
    name = fields.Str(
        required=True,
        validate=[
            validate.Length(min=1, max=255, error="Project name must be between 1 and 255 characters"),
            validate.Regexp(
                r'^[a-zA-Z0-9\s\-_\.]+$', 
                error="Project name can only contain letters, numbers, spaces, hyphens, underscores, and periods"
            )
        ]
    )
    description = fields.Str(
        validate=validate.Length(max=1000, error="Description cannot exceed 1000 characters"),
        allow_none=True
    )
    agent_name = fields.Str(
        validate=validate.Length(max=255, error="Agent name cannot exceed 255 characters"),
        allow_none=True
    )
    agent_role = fields.Str(
        validate=validate.Length(max=500, error="Agent role cannot exceed 500 characters"),
        allow_none=True
    )
    primary_goal = fields.Str(
        validate=validate.Length(max=1000, error="Primary goal cannot exceed 1000 characters"),
        allow_none=True
    )
    goal_steps = fields.Str(
        validate=validate.Length(max=2000, error="Goal steps cannot exceed 2000 characters"),
        allow_none=True
    )
    rules_do = fields.Str(
        validate=validate.Length(max=2000, error="Rules (do) cannot exceed 2000 characters"),
        allow_none=True
    )
    rules_dont = fields.Str(
        validate=validate.Length(max=2000, error="Rules (don't) cannot exceed 2000 characters"),
        allow_none=True
    )
    context_background = fields.Str(
        validate=validate.Length(max=2000, error="Context background cannot exceed 2000 characters"),
        allow_none=True
    )
    output_format = fields.Str(
        validate=validate.Length(max=1000, error="Output format cannot exceed 1000 characters"),
        allow_none=True
    )
    
    @post_load
    def sanitize_fields(self, data, **kwargs):
        """Sanitize all text fields"""
        text_fields = ['name', 'description', 'agent_name', 'agent_role', 
                      'primary_goal', 'goal_steps', 'rules_do', 'rules_dont', 
                      'context_background', 'output_format']
        
        for field in text_fields:
            if field in data and data[field]:
                data[field] = html.escape(data[field].strip())
        
        return data

class ConversationSchema(Schema):
    """Schema for conversation validation"""
    title = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255, error="Title must be between 1 and 255 characters")
    )
    llm_model = fields.Str(
        validate=validate.OneOf([
            'gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini',
            'claude-3.5-sonnet', 'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku',
            'gemini-pro', 'gemini-flash'
        ], error="Invalid model selection"),
        allow_none=True
    )
    project_id = UUIDField(allow_none=True)
    
    @post_load
    def sanitize_title(self, data, **kwargs):
        """Sanitize the title"""
        if 'title' in data:
            data['title'] = html.escape(data['title'].strip())
        return data

class ContextItemSchema(Schema):
    """Schema for context item validation"""
    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255, error="Name must be between 1 and 255 characters")
    )
    description = fields.Str(
        validate=validate.Length(max=1000, error="Description cannot exceed 1000 characters"),
        allow_none=True
    )
    content_type = fields.Str(
        required=True,
        validate=validate.OneOf(['document', 'url', 'text', 'conversation'], 
                               error="Invalid content type")
    )
    content_text = fields.Str(
        validate=validate.Length(max=100000, error="Content cannot exceed 100,000 characters"),
        allow_none=True
    )
    
    @post_load
    def sanitize_fields(self, data, **kwargs):
        """Sanitize text fields"""
        text_fields = ['name', 'description', 'content_text']
        for field in text_fields:
            if field in data and data[field]:
                data[field] = html.escape(data[field].strip())
        return data

class UserPreferencesSchema(Schema):
    """Schema for user preferences validation"""
    defaultModel = fields.Str(
        validate=validate.OneOf([
            'gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini',
            'claude-3.5-sonnet', 'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku',
            'gemini-pro', 'gemini-flash'
        ], error="Invalid default model"),
        allow_none=True
    )
    theme = fields.Str(
        validate=validate.OneOf(['light', 'dark', 'auto'], error="Invalid theme"),
        allow_none=True
    )

class ModelSettingsSchema(Schema):
    """Schema for model settings validation"""
    # Dynamic validation - we'll validate this in the endpoint
    pass

class FileUploadSchema(Schema):
    """Schema for file upload validation"""
    # File validation will be handled in the endpoint
    pass

# Schema instances for reuse
chat_message_schema = ChatMessageSchema()
project_schema = ProjectSchema()
conversation_schema = ConversationSchema()
context_item_schema = ContextItemSchema()
user_preferences_schema = UserPreferencesSchema()
model_settings_schema = ModelSettingsSchema()
file_upload_schema = FileUploadSchema()

def validate_request_data(schema, data):
    """
    Validate request data against a schema
    Returns (validated_data, errors)
    """
    try:
        validated_data = schema.load(data)
        return validated_data, None
    except ValidationError as err:
        return None, err.messages

def create_validation_error_response(errors):
    """
    Create a standardized validation error response
    """
    return {
        'error': 'Validation failed',
        'message': 'The provided data is invalid',
        'validation_errors': errors
    }, 400

def validate_uuid(uuid_string):
    """
    Validate UUID string format
    """
    if not uuid_string:
        return False
    try:
        uuid_lib.UUID(uuid_string)
        return True
    except (ValueError, TypeError):
        return False

def sanitize_filename(filename):
    """
    Sanitize filename for safe storage
    """
    if not filename:
        return None
    
    # Remove path components
    filename = os.path.basename(filename)
    
    # Remove or replace dangerous characters
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext
    
    return filename

def validate_file_upload(file):
    """
    Validate uploaded file
    """
    errors = []
    
    if not file or not file.filename:
        errors.append("No file provided")
        return errors
    
    # Check file size (50MB limit)
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if size > 50 * 1024 * 1024:  # 50MB
        errors.append("File size cannot exceed 50MB")
    
    # Check file type
    allowed_types = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
        'text/plain',
        'text/csv',
        'text/markdown',
        'text/x-markdown',
        'application/json'
    ]
    
    if file.content_type not in allowed_types:
        errors.append(f"File type '{file.content_type}' not allowed")
    
    # Check filename
    if not sanitize_filename(file.filename):
        errors.append("Invalid filename")
    
    return errors
