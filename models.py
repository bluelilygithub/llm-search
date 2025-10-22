from database import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from pgvector.sqlalchemy import Vector

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # Structured prompt template fields
    agent_name = db.Column(db.String(255))
    agent_role = db.Column(db.String(500))
    agent_personality = db.Column(db.String(500))
    primary_goal = db.Column(db.Text)
    goal_steps = db.Column(db.Text)  # JSON array of steps
    rules_do = db.Column(db.Text)    # JSON array of DO rules
    rules_dont = db.Column(db.Text)  # JSON array of DON'T rules
    context_background = db.Column(db.Text)
    user_role = db.Column(db.String(500))
    output_format = db.Column(db.Text)
    
    # User ownership
    owner_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=True, index=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conversations = db.relationship('Conversation', backref='project', lazy=True, cascade='all, delete-orphan')
    owner = db.relationship('User', backref='projects', foreign_keys=[owner_id])

class Conversation(db.Model):
    __tablename__ = 'conversations'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id'), nullable=True)  # New field
    title = db.Column(db.String(255), nullable=False)
    llm_model = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tags = db.Column(db.JSON, default=list)
    context_documents = db.Column(db.JSON, default=None)  # New: stores uploaded context docs as list of dicts
    # User identification - linked to users table
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=True, index=True)  # For authenticated users
    # Legacy fields for migration (will be deprecated)
    session_id = db.Column(db.String(100), nullable=True)  # Legacy: For free/anonymous users
    ip_address = db.Column(db.String(45), nullable=True)  # Legacy: Additional tracking for free users
    # RAG: Vector embedding for conversation summary (for semantic search)
    # Temporarily disabled - uncomment after confirming migration worked
    # embedding = db.Column(Vector(1536), nullable=True)
    # embedding_processed = db.Column(db.Boolean, default=False)
    # embedding_processed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade='all, delete-orphan')
    user = db.relationship('User', backref='conversations', foreign_keys=[user_id])

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = db.Column(UUID(as_uuid=True), db.ForeignKey('conversations.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    # RAG: Vector embedding for message content (for semantic search)
    # Temporarily disabled - uncomment after confirming migration worked
    # embedding = db.Column(Vector(1536), nullable=True)
    # embedding_processed = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    attachments = db.relationship('Attachment', backref='message', lazy=True, cascade='all, delete-orphan')

class Attachment(db.Model):
    __tablename__ = 'attachments'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = db.Column(UUID(as_uuid=True), db.ForeignKey('messages.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    processed_content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SearchQuery(db.Model):
    __tablename__ = 'search_queries'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_text = db.Column(db.Text, nullable=False)
    # query_embedding = db.Column(Vector(1536))  # Will add back with pgvector
    results_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LLMUsageLog(db.Model):
    __tablename__ = 'llm_usage_logs'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    tokens = db.Column(db.Integer, nullable=True)
    estimated_cost = db.Column(db.Float, nullable=True)
    conversation_id = db.Column(UUID(as_uuid=True), db.ForeignKey('conversations.id'), nullable=True)

class LLMErrorLog(db.Model):
    __tablename__ = 'llm_error_logs'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    error_message = db.Column(db.Text, nullable=False)
    conversation_id = db.Column(UUID(as_uuid=True), db.ForeignKey('conversations.id'), nullable=True)

class FreeAccessLog(db.Model):
    __tablename__ = 'free_access_logs'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(db.String(255), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True, index=True)  # IPv6 support
    user_agent = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    model = db.Column(db.String(100), nullable=False)
    query_count = db.Column(db.Integer, default=1)
    tracking_key = db.Column(db.String(64), nullable=True, index=True)  # Combined IP+UA hash
    
    # Index for efficient queries
    __table_args__ = (
        db.Index('idx_session_timestamp', 'session_id', 'timestamp'),
        db.Index('idx_ip_timestamp', 'ip_address', 'timestamp'),
        db.Index('idx_tracking_key_timestamp', 'tracking_key', 'timestamp'),
    )

class IPWhitelist(db.Model):
    __tablename__ = 'ip_whitelist'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip_address = db.Column(db.String(45), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255), nullable=True)  # e.g., "Demo office", "John's home"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100), nullable=True)  # Who added this IP
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
class IPUsageSummary(db.Model):
    __tablename__ = 'ip_usage_summary'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    total_queries = db.Column(db.Integer, default=0)
    unique_sessions = db.Column(db.Integer, default=0)
    last_user_agent = db.Column(db.Text, nullable=True)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Compound unique index
    __table_args__ = (
        db.UniqueConstraint('ip_address', 'date', name='unique_ip_date'),
        db.Index('idx_ip_date', 'ip_address', 'date'),
    )

# Context Management Models
class ContextItem(db.Model):
    __tablename__ = 'context_items'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.String(255), nullable=False, index=True)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    content_type = db.Column(db.String(50), nullable=False)  # 'document', 'url', 'text', 'conversation'
    content_text = db.Column(db.Text)
    content_summary = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    original_filename = db.Column(db.String(255))
    file_size = db.Column(db.Integer)
    token_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    extra_data = db.Column(db.JSON)  # Store additional metadata as JSON
    
    # Relationships
    project = db.relationship('Project', backref='context_items')

class ContextSession(db.Model):
    __tablename__ = 'context_sessions'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = db.Column(UUID(as_uuid=True), db.ForeignKey('conversations.id', ondelete='CASCADE'))
    context_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey('context_items.id', ondelete='CASCADE'))
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    added_by = db.Column(db.String(50), default='user')  # 'user', 'system', 'suggestion'
    is_active = db.Column(db.Boolean, default=True)
    relevance_score = db.Column(db.Numeric(3, 2), default=1.0)  # 0.0 to 1.0
    tokens_used = db.Column(db.Integer, default=0)
    last_accessed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    conversation = db.relationship('Conversation', backref='context_sessions')
    context_item = db.relationship('ContextItem', backref='sessions')

class ContextUsageLog(db.Model):
    __tablename__ = 'context_usage_logs'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = db.Column(UUID(as_uuid=True), db.ForeignKey('conversations.id', ondelete='CASCADE'))
    message_id = db.Column(UUID(as_uuid=True), db.ForeignKey('messages.id', ondelete='CASCADE'))
    context_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey('context_items.id', ondelete='CASCADE'))
    usage_type = db.Column(db.String(50), nullable=False)  # 'input', 'reference', 'citation'
    influence_score = db.Column(db.Numeric(3, 2), default=0.0)  # How much this context influenced response
    tokens_consumed = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    conversation = db.relationship('Conversation', backref='context_usage_logs')
    message = db.relationship('Message', backref='context_usage_logs')
    context_item = db.relationship('ContextItem', backref='usage_logs')

class ContextTemplate(db.Model):
    __tablename__ = 'context_templates'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    context_items = db.Column(db.JSON, nullable=False)  # Array of context_item_ids
    is_public = db.Column(db.Boolean, default=False)
    usage_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class Template(db.Model):
    __tablename__ = 'templates'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.String(255), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    default_model = db.Column(db.String(100))
    description = db.Column(db.Text)
    icon = db.Column(db.String(100), default='fas fa-file-alt')  # FontAwesome icon class
    usage_count = db.Column(db.Integer, default=0)
    is_public = db.Column(db.Boolean, default=False)  # For sharing templates
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Index for efficient queries
    __table_args__ = (
        db.Index('idx_user_category', 'user_id', 'category'),
        db.Index('idx_public_active', 'is_public', 'is_active'),
    )

class ContextAnalytics(db.Model):
    __tablename__ = 'context_analytics'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.String(255), nullable=False)
    date = db.Column(db.Date, nullable=False)
    total_items = db.Column(db.Integer, default=0)
    items_used = db.Column(db.Integer, default=0)
    total_tokens_consumed = db.Column(db.Integer, default=0)
    most_used_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey('context_items.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    most_used_item = db.relationship('ContextItem', backref='analytics_records')
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', name='unique_user_date'),
    )

class ModelSettings(db.Model):
    __tablename__ = 'model_settings'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    status = db.Column(db.String(50), default='unknown')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'enabled': self.enabled,
            'status': self.status
        }

class DocumentEmbedding(db.Model):
    __tablename__ = 'document_embeddings'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    context_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey('context_items.id', ondelete='CASCADE'), nullable=False, index=True)
    chunk_index = db.Column(db.Integer, nullable=False)
    chunk_text = db.Column(db.Text, nullable=False)
    chunk_tokens = db.Column(db.Integer, default=0)
    embedding = db.Column(db.JSON)  # Store as JSON array (PostgreSQL vector would be better but requires extension)
    chunk_metadata = db.Column(db.JSON)  # Renamed from 'metadata' to avoid SQLAlchemy conflict
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    context_item = db.relationship('ContextItem', backref='embeddings')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'context_item_id': str(self.context_item_id),
            'chunk_index': self.chunk_index,
            'chunk_text': self.chunk_text,
            'chunk_tokens': self.chunk_tokens,
            'chunk_metadata': self.chunk_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }