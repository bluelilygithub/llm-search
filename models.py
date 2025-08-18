from app import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = db.Column(db.String(255), nullable=False)
    llm_model = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tags = db.Column(db.JSON, default=list)
    
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