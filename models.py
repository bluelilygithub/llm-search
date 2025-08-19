from database import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    conversations = db.relationship('Conversation', backref='project', lazy=True, cascade='all, delete-orphan')

class Conversation(db.Model):
    __tablename__ = 'conversations'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id'), nullable=True)  # New field
    title = db.Column(db.String(255), nullable=False)
    llm_model = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tags = db.Column(db.JSON, default=list)
    context_documents = db.Column(db.JSON, default=list)  # New: stores uploaded context docs as list of dicts
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade='all, delete-orphan')

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = db.Column(UUID(as_uuid=True), db.ForeignKey('conversations.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    # embeddings = db.Column(Vector(1536))  # Will add back with pgvector
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