from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import Config
import uuid
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
CORS(app)

from models import Conversation, Message, Attachment

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'message': 'AI Knowledge Base API is running'})

@app.route('/')
def index():
    return jsonify({'message': 'AI Knowledge Base Interface', 'version': '1.0.0'})

@app.route('/init-db')
def init_database():
    try:
        db.create_all()
        return jsonify({'message': 'Database initialized successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/conversations', methods=['GET'])
def get_conversations():
    conversations = Conversation.query.order_by(Conversation.updated_at.desc()).all()
    return jsonify([{
        'id': str(conv.id),
        'title': conv.title,
        'llm_model': conv.llm_model,
        'created_at': conv.created_at.isoformat(),
        'updated_at': conv.updated_at.isoformat(),
        'tags': conv.tags or [],
        'message_count': len(conv.messages)
    } for conv in conversations])

@app.route('/conversations', methods=['POST'])
def create_conversation():
    data = request.get_json()
    
    if not data or not data.get('title') or not data.get('llm_model'):
        return jsonify({'error': 'Title and llm_model are required'}), 400
    
    conversation = Conversation(
        title=data['title'],
        llm_model=data['llm_model'],
        tags=data.get('tags', [])
    )
    
    db.session.add(conversation)
    db.session.commit()
    
    return jsonify({
        'id': str(conversation.id),
        'title': conversation.title,
        'llm_model': conversation.llm_model,
        'created_at': conversation.created_at.isoformat(),
        'tags': conversation.tags
    }), 201

@app.route('/conversations/<conversation_id>/messages', methods=['GET'])
def get_messages(conversation_id):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        return jsonify({'error': 'Invalid conversation ID'}), 400
    
    conversation = Conversation.query.get_or_404(conv_uuid)
    messages = Message.query.filter_by(conversation_id=conv_uuid).order_by(Message.timestamp.asc()).all()
    
    return jsonify({
        'conversation': {
            'id': str(conversation.id),
            'title': conversation.title,
            'llm_model': conversation.llm_model
        },
        'messages': [{
            'id': str(msg.id),
            'role': msg.role,
            'content': msg.content,
            'timestamp': msg.timestamp.isoformat()
        } for msg in messages]
    })

@app.route('/conversations/<conversation_id>/messages', methods=['POST'])
def add_message(conversation_id):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        return jsonify({'error': 'Invalid conversation ID'}), 400
    
    conversation = Conversation.query.get_or_404(conv_uuid)
    data = request.get_json()
    
    if not data or not data.get('role') or not data.get('content'):
        return jsonify({'error': 'Role and content are required'}), 400
    
    if data['role'] not in ['user', 'assistant']:
        return jsonify({'error': 'Role must be user or assistant'}), 400
    
    message = Message(
        conversation_id=conv_uuid,
        role=data['role'],
        content=data['content']
    )
    
    conversation.updated_at = datetime.utcnow()
    
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'id': str(message.id),
        'role': message.role,
        'content': message.content,
        'timestamp': message.timestamp.isoformat()
    }), 201

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)