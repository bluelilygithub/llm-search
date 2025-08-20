from flask import Flask, jsonify, request, render_template, send_from_directory, redirect, url_for
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
import uuid
from datetime import datetime
import os
import re
import html
from werkzeug.utils import secure_filename

from PyPDF2 import PdfReader
import io
try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

# Initialize Flask app
app = Flask(__name__, static_folder='static')

# Configure app based on environment
from config import config
config_name = os.getenv('FLASK_CONFIG', 'default')
app.config.from_object(config[config_name])
config[config_name].init_app(app)

# Security configurations
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Setup logging
from logger import setup_logging
setup_logging(app)

# Initialize database
from database import db, init_db
db = init_db(app)

CORS(app)

# Rate limiting - use in-memory for simplicity
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"]
)
limiter.init_app(app)

# Import models after db initialization
from models import Conversation, Message, Attachment, Project
from context_service import ContextService
from llm_service import LLMService

# Initialize authentication
from auth import auth
auth.init_app(app)

llm_service = LLMService()

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'message': 'AI Knowledge Base API is running'})

@app.route('/')
def index():
    has_access, access_type, free_info = auth.has_access()
    if not has_access:
        return redirect(url_for('login_page'))
    return render_template('index.html')

@app.route('/login')
def login_page():
    if auth.is_authenticated():
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/init-db')
def init_database():
    try:
        db.create_all()
        return jsonify({'message': 'Database initialized successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/projects', methods=['GET'])
@auth.login_required
def get_projects():
    from models import Project
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return jsonify([
        {
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat() if project.updated_at else None
        }
        for project in projects
    ])

@app.route('/projects', methods=['POST'])
def create_project():
    from models import Project
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Project name is required'}), 400
    project = Project(
        name=data['name'],
        description=data.get('description', '')
    )
    db.session.add(project)
    db.session.commit()
    return jsonify({
        'id': str(project.id),
        'name': project.name,
        'description': project.description,
        'created_at': project.created_at.isoformat(),
        'updated_at': project.updated_at.isoformat() if project.updated_at else None
    }), 201

@app.route('/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    from models import Project, Conversation
    project = Project.query.get_or_404(project_id)
    # Set project_id to None for all related conversations
    Conversation.query.filter_by(project_id=project_id).update({'project_id': None})
    db.session.delete(project)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/projects/<project_id>', methods=['PATCH'])
def rename_project(project_id):
    from models import Project
    project = Project.query.get_or_404(project_id)
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Project name is required'}), 400
    project.name = data['name']
    if 'description' in data:
        project.description = data['description']
    db.session.commit()
    return jsonify({
        'id': str(project.id),
        'name': project.name,
        'description': project.description,
        'created_at': project.created_at.isoformat(),
        'updated_at': project.updated_at.isoformat() if project.updated_at else None
    })

@app.route('/conversations', methods=['GET'])
@auth.login_required
def get_conversations():
    project_id = request.args.get('project_id')
    query = Conversation.query
    if project_id:
        query = query.filter_by(project_id=project_id)
    conversations = query.order_by(Conversation.updated_at.desc()).all()
    return jsonify([
        {
            'id': str(conv.id),
            'project_id': str(conv.project_id) if conv.project_id else None,
            'title': conv.title,
            'llm_model': conv.llm_model,
            'created_at': conv.created_at.isoformat(),
            'updated_at': conv.updated_at.isoformat(),
            'tags': conv.tags or [],
            'message_count': len(conv.messages)
        }
        for conv in conversations
    ])

# Update create_conversation to accept project_id
@app.route('/conversations', methods=['POST'])
def create_conversation():
    data = request.get_json()
    if not data or not data.get('title') or not data.get('llm_model'):
        return jsonify({'error': 'Title and llm_model are required'}), 400
    from models import Conversation
    conversation = Conversation(
        title=data['title'],
        llm_model=data['llm_model'],
        tags=data.get('tags', []),
        project_id=data.get('project_id')
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

@app.route('/chat', methods=['POST'])
@limiter.limit("30 per minute")
@auth.access_required(allow_free=True)
def chat():
    try:
        data = request.get_json()
        
        if not data or not data.get('message') or not data.get('model'):
            return jsonify({'error': 'Message and model are required'}), 400
        
        conversation_id = data.get('conversation_id')
        user_message = data['message']
        model = data['model']
        
        # Handle free tier access
        if getattr(request, 'access_type', None) == 'free_tier':
            from auth import FreeAccessManager
            free_info = FreeAccessManager.log_free_query(model)
            app.logger.info(f"Free tier chat: model={model}, remaining={free_info['queries_remaining']}")
        
        app.logger.info(f"Chat request: model={model}, message_length={len(user_message)}")
        
        # Get conversation history if conversation exists
        messages = []
        if conversation_id:
            conv_uuid = uuid.UUID(conversation_id)
            conversation = Conversation.query.get_or_404(conv_uuid)
            db_messages = Message.query.filter_by(conversation_id=conv_uuid).order_by(Message.timestamp.asc()).all()
            messages = llm_service.format_conversation_for_llm(db_messages)
            # Add context items to prompt using new context management system
            try:
                active_context = ContextService.get_conversation_context(str(conversation_id))
                if active_context:
                    # Build comprehensive context system message
                    context_content = []
                    for ctx in active_context:
                        context_content.append(f"""
=== {ctx['name']} ===
Type: {ctx['content_type']}
{f"Description: {ctx['description']}" if ctx['description'] else ""}

{ctx['content_text']}
""")
                    
                    if context_content:
                        system_msg = f"""You have access to the following context documents for this conversation. Use this information to inform your responses:

{chr(10).join(context_content)}

---
Please use this context information appropriately when responding to user questions. If the user asks you to create content based on guidelines, use the provided guidelines. If they ask about document content, reference the documents above."""
                        
                        messages.insert(0, {
                            'role': 'system',
                            'content': system_msg
                        })
                        
                        app.logger.info(f"Added {len(active_context)} context items to conversation {conversation_id}")
                    
            except Exception as context_error:
                app.logger.error(f"Failed to load context for conversation {conversation_id}: {context_error}")
            
            # Fallback to old context_documents system for backward compatibility
            import json
            docs = getattr(conversation, 'context_documents', None)
            if isinstance(docs, str):
                try:
                    docs = json.loads(docs)
                except Exception:
                    docs = []
            if docs and not active_context:  # Only use old system if new system has no context
                for doc in docs:
                    if doc and 'content' in doc:
                        task_type = doc.get('task_type', 'instructions')
                        filename = doc.get('filename', 'uploaded file')
                        content = doc['content']
                        
                        if task_type == 'summary':
                            system_msg = f"You have been provided with a document ({filename}) to summarize. You can analyze, count words, and provide detailed summaries of this content:\n\n{content}"
                        elif task_type == 'analysis':
                            system_msg = f"You have been provided with a document ({filename}) to analyze. You can examine, count words, and provide detailed analysis of this content:\n\n{content}"
                        else:
                            system_msg = f"Document reference ({filename}): You have access to this document content and can answer questions about it, count words, analyze it, or use it as guidelines:\n\n{content}"
                        
                        messages.insert(0, {
                            'role': 'system',
                            'content': system_msg
                        })
        # Log prompt details
        app.logger.debug(f"LLM request with {len(messages)} messages for model {model}")
        
        # Add current user message
        messages.append({'role': 'user', 'content': user_message})
        
        app.logger.info(f"Calling LLM service for model: {model}")
        # Get AI response and usage info
        ai_response, tokens, estimated_cost = llm_service.get_response(model, messages)
        app.logger.info(f"Got response from {model}: {tokens} tokens, cost: ${estimated_cost:.4f}")
        
        # Log usage
        from models import LLMUsageLog
        usage_log = LLMUsageLog(
            model=model,
            conversation_id=conversation_id if conversation_id else None,
            tokens=tokens,
            estimated_cost=estimated_cost
        )
        db.session.add(usage_log)
        
        # Log context usage if conversation exists and context was used
        if conversation_id:
            try:
                active_context = ContextService.get_conversation_context(str(conversation_id))
                if active_context:
                    # Create a message ID for logging (since we don't save the user message yet)
                    temp_message_id = str(uuid.uuid4())
                    
                    for ctx in active_context:
                        ContextService.log_context_usage(
                            conversation_id=str(conversation_id),
                            message_id=temp_message_id,
                            context_item_id=ctx['item_id'],
                            usage_type='input',
                            influence_score=1.0,  # Could be refined later
                            tokens_consumed=ctx['token_count']
                        )
            except Exception as log_error:
                app.logger.error(f"Failed to log context usage: {log_error}")
        
        db.session.commit()
        
        # Prepare response
        response_data = {
            'response': ai_response,
            'model': model,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Add updated free access info if applicable
        if getattr(request, 'access_type', None) == 'free_tier':
            from auth import FreeAccessManager
            updated_free_info = FreeAccessManager.check_free_access()
            response_data['free_access'] = updated_free_info
        
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Chat error: {str(e)}", exc_info=True)
        # Log error to database
        try:
            from models import LLMErrorLog
            error_log = LLMErrorLog(
                model=model if 'model' in locals() else 'unknown',
                conversation_id=conversation_id if 'conversation_id' in locals() and conversation_id else None,
                error_message=str(e)
            )
            db.session.add(error_log)
            db.session.commit()
        except Exception as db_error:
            app.logger.error(f"Failed to log error to database: {db_error}")
        return jsonify({'error': str(e)}), 500

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']
        app.logger.info(f'Audio transcription request: {audio_file.filename}, Content-Type: {audio_file.content_type}')
        if audio_file.filename == '':
            return jsonify({'error': 'No audio file selected'}), 400

        # Supported formats for Google Speech-to-Text
        SUPPORTED_FORMATS = ['flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm']
        ext = audio_file.filename.rsplit('.', 1)[-1].lower()
        if ext not in SUPPORTED_FORMATS:
            return jsonify({
                'error': f'Unsupported file format: .{ext}. Supported formats: {SUPPORTED_FORMATS}'
            }), 400

        from google.cloud import speech
        import io

        client = speech.SpeechClient()
        audio_content = audio_file.read()
        audio = speech.RecognitionAudio(content=audio_content)

        # Use OGG_OPUS encoding for .ogg and .webm, LINEAR16 for others
        if ext in ['ogg', 'webm']:
            encoding = speech.RecognitionConfig.AudioEncoding.OGG_OPUS
            sample_rate = 48000  # Opus is usually 48000 Hz
        else:
            encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16
            sample_rate = 16000  # Default for LINEAR16

        config = speech.RecognitionConfig(
            encoding=encoding,
            sample_rate_hertz=sample_rate,
            language_code="en-US",
        )

        response = client.recognize(config=config, audio=audio)

        transcription = ''
        for result in response.results:
            transcription += result.alternatives[0].transcript + ' '

        return jsonify({
            'transcription': transcription.strip(),
            'success': True
        })

    except Exception as e:
        app.logger.error(f"Transcription error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/conversations/<conversation_id>/attachments', methods=['POST'])
def upload_attachments(conversation_id):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        return jsonify({'error': 'Invalid conversation ID'}), 400
    conversation = Conversation.query.get_or_404(conv_uuid)
    if 'files' not in request.files:
        return jsonify({'error': 'No files part in the request'}), 400
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    attachments = []
    try:
        for file in files:
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            # Ensure unique filename
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(file_path):
                filename = f"{base}_{counter}{ext}"
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                counter += 1
            file.save(file_path)
            # Create a new message for the attachment (role='user', content='[file upload]')
            message = Message(
                conversation_id=conv_uuid,
                role='user',
                content=f'[File uploaded: {filename}]'
            )
            db.session.add(message)
            db.session.flush()  # Get message.id
            attachment = Attachment(
                message_id=message.id,
                filename=filename,
                content_type=file.content_type,
                file_path=os.path.relpath(file_path, os.getcwd()),
                created_at=datetime.utcnow()  # Ensure created_at is set
            )
            db.session.add(attachment)
            attachments.append({
                'id': str(attachment.id),
                'filename': filename,
                'content_type': file.content_type,
                'file_path': attachment.file_path,
                'created_at': attachment.created_at.isoformat() if hasattr(attachment, 'created_at') else datetime.utcnow().isoformat()
            })
        db.session.commit()
        return jsonify({'attachments': attachments}), 201
    except Exception as e:
        app.logger.error(f"Attachment upload error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def sanitize_content(content):
    """Sanitize extracted content to prevent security issues"""
    if not content:
        return content
    
    # Limit content size to prevent memory issues
    MAX_CONTENT_SIZE = 5 * 1024 * 1024  # 5MB text limit
    if len(content) > MAX_CONTENT_SIZE:
        content = content[:MAX_CONTENT_SIZE] + "\n\n[Content truncated for security...]"
    
    # Remove potentially malicious patterns
    content = html.escape(content)  # Escape HTML entities
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'<iframe[^>]*>.*?</iframe>', '', content, flags=re.DOTALL | re.IGNORECASE)
    
    # Clean up excessive whitespace
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    content = content.strip()
    
    return content

def extract_document_content(file, filename):
    """Generic document content extractor - supports PDF, DOCX, TXT, MD, CSV"""
    ext = filename.rsplit('.', 1)[-1].lower()
    content = ''
    
    try:
        if ext == 'pdf':
            reader = PdfReader(file)
            content = '\n'.join(page.extract_text() or '' for page in reader.pages)
        elif ext in ['docx', 'doc'] and DocxDocument:
            doc = DocxDocument(file)
            content = '\n'.join([p.text for p in doc.paragraphs])
        elif ext in ['txt', 'md', 'csv']:
            content = file.read().decode('utf-8', errors='ignore')
        else:
            raise ValueError(f'Unsupported file type: .{ext}')
    except Exception as e:
        raise Exception(f'Failed to extract text from {filename}: {e}')
    
    return sanitize_content(content)

@app.route('/upload-context', methods=['POST'])
@limiter.limit("10 per minute")
def upload_context():
    conversation_id = request.form.get('conversation_id')
    task_type = request.form.get('task_type', 'instructions')  # New: instructions, summary, analysis, etc.
    
    # Upload logging removed for security
    
    if not conversation_id:
        return jsonify({'error': 'Missing conversation_id'}), 400
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        return jsonify({'error': 'Invalid conversation ID'}), 400
    
    conversation = Conversation.query.get_or_404(conv_uuid)
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    filename = secure_filename(file.filename)
    
    try:
        # Use generic content extractor
        content = extract_document_content(file, filename)
        
        # Apply task-specific processing
        processed_content = process_document_by_task(content, filename, task_type)
        
        # Create context item using new context management system
        try:
            context_item = ContextService.create_context_item(
                name=filename,
                content_type='document',
                content_text=processed_content,
                description=f"Uploaded document - {task_type}",
                original_filename=filename,
                file_size=len(content) if content else 0,
                extra_data={
                    'task_type': task_type,
                    'original_content': content[:1000] if content else None  # Store first 1000 chars of original
                }
            )
            
            # Automatically add context item to current conversation
            ContextService.add_context_to_conversation(
                conversation_id=conversation_id,
                context_item_id=str(context_item.id),
                relevance_score=1.0
            )
            
            app.logger.info(f"Created context item {context_item.id} for conversation {conversation_id}")
            
        except Exception as context_error:
            app.logger.error(f"Failed to create context item: {context_error}")
            # Continue with old system as fallback
        
        # Keep old system for backward compatibility
        import json
        docs = conversation.context_documents
        
        if not docs:
            docs = []
        elif isinstance(docs, str):
            try:
                docs = json.loads(docs)
            except Exception:
                docs = []
        if not isinstance(docs, list):
            docs = []
        
        docs.append({
            'filename': filename, 
            'content': processed_content,
            'task_type': task_type,
            'original_content': content  # Keep original for reference
        })
        
        conversation.context_documents = docs
        db.session.commit()
        
        # Get file type for icon
        file_type = get_file_type(filename)
        word_count = len(content.split()) if content else 0
        
        # Upload metadata logging removed for security
        
        preview = processed_content[:500] + ('...' if len(processed_content) > 500 else '')
        response_data = {
            'success': True, 
            'filename': filename, 
            'preview': preview,
            'task_type': task_type,
            'file_type': file_type,
            'file_size': len(content),
            'word_count': word_count
        }
        
        # Response logging removed for security
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Context extraction error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def get_file_type(filename):
    """Get file type for icon display"""
    ext = filename.rsplit('.', 1)[-1].lower()
    
    file_types = {
        'pdf': 'pdf',
        'doc': 'word', 'docx': 'word',
        'txt': 'text', 'md': 'text', 'csv': 'text',
        'jpg': 'image', 'jpeg': 'image', 'png': 'image', 'gif': 'image',
        'mp3': 'audio', 'wav': 'audio', 'm4a': 'audio',
        'mp4': 'video', 'avi': 'video', 'mov': 'video'
    }
    
    return file_types.get(ext, 'file')

def process_document_by_task(content, filename, task_type):
    """Process document content based on intended task"""
    
    task_prompts = {
        'instructions': f"Use this document as guidelines and instructions for your responses:\n\n{content}",
        'summary': f"Please summarize the following document ({filename}):\n\n{content}",
        'analysis': f"Please analyze the following document ({filename}):\n\n{content}",
        'reference': f"Reference document ({filename}) - use this information to answer questions:\n\n{content}",
        'template': f"Use this document as a template or example ({filename}):\n\n{content}"
    }
    
    return task_prompts.get(task_type, f"Document ({filename}):\n\n{content}")

@app.route('/extract-url', methods=['POST'])
@limiter.limit("5 per minute")
def extract_url_content():
    """Extract content from a URL and add it as context"""
    data = request.get_json()
    
    if not data or not data.get('url') or not data.get('conversation_id'):
        return jsonify({'error': 'URL and conversation_id are required'}), 400
    
    url = data['url']
    conversation_id = data['conversation_id']
    task_type = data.get('task_type', 'reference')
    
    try:
        conv_uuid = uuid.UUID(conversation_id)
        conversation = Conversation.query.get_or_404(conv_uuid)
        
        # Extract content from URL using requests and basic HTML parsing
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Try with different approaches if first fails
        session = requests.Session()
        session.headers.update(headers)
        
        try:
            response = session.get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
        except requests.exceptions.SSLError:
            # Try without SSL verification as fallback
            response = session.get(url, timeout=15, allow_redirects=True, verify=False)
            response.raise_for_status()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            # Try with HTTP instead of HTTPS
            if url.startswith('https://'):
                http_url = url.replace('https://', 'http://', 1)
                response = session.get(http_url, timeout=15, allow_redirects=True)
                response.raise_for_status()
            else:
                raise
        
        # Check content size
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB limit
            return jsonify({'error': 'URL content too large (max 10MB)'}), 400
        
        # Parse HTML and extract text
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text content
        content = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in content.splitlines())
        content = '\n'.join(line for line in lines if line)
        
        # Sanitize the extracted content
        content = sanitize_content(content)
        
        if not content:
            return jsonify({'error': 'No readable content found at URL'}), 400
        
        # Process content like uploaded documents
        processed_content = process_document_by_task(content, url, task_type)
        
        # Add to conversation context
        import json
        docs = conversation.context_documents
        if not docs:
            docs = []
        elif isinstance(docs, str):
            try:
                docs = json.loads(docs)
            except Exception:
                docs = []
        if not isinstance(docs, list):
            docs = []
        
        docs.append({
            'filename': url,
            'content': processed_content,
            'task_type': task_type,
            'original_content': content,
            'source_type': 'url'
        })
        
        conversation.context_documents = docs
        db.session.commit()
        
        # Extract title for display
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else url
        
        word_count = len(content.split()) if content else 0
        preview = content[:500] + ('...' if len(content) > 500 else '')
        
        return jsonify({
            'success': True,
            'url': url,
            'title': title,
            'preview': preview,
            'word_count': word_count,
            'task_type': task_type
        })
        
    except requests.RequestException as e:
        status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        error_str = str(e).lower()
        
        if status_code == 403:
            return jsonify({'error': 'Website blocked access. Try copying and pasting the content instead, or use a different URL.'}), 400
        elif status_code == 404:
            return jsonify({'error': 'URL not found (404). Please check the URL is correct.'}), 400
        elif status_code == 429:
            return jsonify({'error': 'Website rate limited our request. Please try again later.'}), 400
        elif 'connection aborted' in error_str or 'remote end closed' in error_str:
            return jsonify({'error': 'Website closed connection. The site may be down or blocking automated access. Try copying the content manually.'}), 400
        elif 'timeout' in error_str:
            return jsonify({'error': 'Website took too long to respond. Please try again or use a different URL.'}), 400
        elif 'ssl' in error_str:
            return jsonify({'error': 'SSL certificate issue. The website may have security problems.'}), 400
        else:
            return jsonify({'error': f'Failed to fetch URL: {str(e)}'}), 400
    except Exception as e:
        app.logger.error(f"URL extraction error: {e}", exc_info=True)
        return jsonify({'error': f'Failed to process URL: {str(e)}'}), 500

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/llm-usage-stats', methods=['GET'])
def llm_usage_stats():
    from models import LLMUsageLog
    from sqlalchemy import func, cast, Date
    import datetime
    # Aggregate by model (existing)
    stats = db.session.query(
        LLMUsageLog.model,
        func.count().label('calls'),
        func.coalesce(func.sum(LLMUsageLog.tokens), 0).label('total_tokens'),
        func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0.0).label('total_cost')
    ).group_by(LLMUsageLog.model).all()
    result = [
        {
            'model': row.model,
            'calls': row.calls,
            'total_tokens': row.total_tokens,
            'total_cost': float(row.total_cost)
        }
        for row in stats
    ]
    # Aggregate by day and model for the last 14 days
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=13)
    timeseries = db.session.query(
        cast(LLMUsageLog.timestamp, Date).label('date'),
        LLMUsageLog.model,
        func.count().label('calls'),
        func.coalesce(func.sum(LLMUsageLog.tokens), 0).label('tokens'),
        func.coalesce(func.sum(LLMUsageLog.estimated_cost), 0.0).label('cost')
    ).filter(LLMUsageLog.timestamp >= start_date).group_by('date', LLMUsageLog.model).order_by('date').all()
    timeseries_result = [
        {
            'date': row.date.isoformat(),
            'model': row.model,
            'calls': row.calls,
            'tokens': row.tokens,
            'cost': float(row.cost)
        }
        for row in timeseries
    ]
    return jsonify({'stats': result, 'timeseries': timeseries_result})

@app.route('/llm-error-log', methods=['GET'])
def llm_error_log():
    from models import LLMErrorLog
    errors = LLMErrorLog.query.order_by(LLMErrorLog.timestamp.desc()).limit(20).all()
    result = [
        {
            'timestamp': e.timestamp.isoformat(),
            'model': e.model,
            'error_message': e.error_message,
            'conversation_id': str(e.conversation_id) if e.conversation_id else None
        }
        for e in errors
    ]
    return jsonify({'errors': result})

@app.route('/api/log-error', methods=['POST'])
def log_client_error():
    """Log client-side JavaScript errors"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Log the client error
        app.logger.error(
            f"Client Error: {data.get('type', 'Unknown')} - {data.get('message', 'No message')} "
            f"URL: {data.get('url', 'Unknown')} "
            f"User-Agent: {data.get('userAgent', 'Unknown')}"
        )
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        app.logger.error(f"Failed to log client error: {e}")
        return jsonify({'error': 'Failed to log error'}), 500

# Admin IP Management Endpoints
@app.route('/admin/whitelist', methods=['GET'])
@auth.login_required
def get_ip_whitelist():
    """Get all whitelisted IPs"""
    from models import IPWhitelist
    whitelist = IPWhitelist.query.filter_by(is_active=True).order_by(IPWhitelist.created_at.desc()).all()
    
    return jsonify([
        {
            'id': str(entry.id),
            'ip_address': entry.ip_address,
            'description': entry.description,
            'created_at': entry.created_at.isoformat(),
            'created_by': entry.created_by
        }
        for entry in whitelist
    ])

@app.route('/admin/whitelist', methods=['POST'])
@auth.login_required
def add_ip_to_whitelist():
    """Add IP to whitelist"""
    from auth import FreeAccessManager
    
    data = request.get_json()
    if not data or not data.get('ip_address'):
        return jsonify({'error': 'IP address is required'}), 400
    
    ip_address = data['ip_address'].strip()
    description = data.get('description', 'Demo Access')
    created_by = data.get('created_by', 'admin')
    
    success, message = FreeAccessManager.add_to_whitelist(ip_address, description, created_by)
    
    if success:
        return jsonify({'message': message}), 201
    else:
        return jsonify({'error': message}), 400

@app.route('/admin/whitelist/<ip_address>', methods=['DELETE'])
@auth.login_required  
def remove_ip_from_whitelist(ip_address):
    """Remove IP from whitelist"""
    from auth import FreeAccessManager
    
    success, message = FreeAccessManager.remove_from_whitelist(ip_address)
    
    if success:
        return jsonify({'message': message})
    else:
        return jsonify({'error': message}), 404

@app.route('/admin/usage-stats', methods=['GET'])
@auth.login_required
def get_usage_stats():
    """Get comprehensive usage statistics"""
    from models import IPUsageSummary, FreeAccessLog, IPWhitelist
    from sqlalchemy import func, desc
    from datetime import datetime, timedelta
    
    # Get top IPs by usage in last 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    top_ips = db.session.query(
        FreeAccessLog.ip_address,
        func.count(FreeAccessLog.id).label('total_queries'),
        func.count(func.distinct(FreeAccessLog.session_id)).label('unique_sessions'),
        func.max(FreeAccessLog.timestamp).label('last_activity')
    ).filter(
        FreeAccessLog.timestamp >= week_ago
    ).group_by(
        FreeAccessLog.ip_address
    ).order_by(
        desc('total_queries')
    ).limit(20).all()
    
    # Get whitelist count
    whitelist_count = IPWhitelist.query.filter_by(is_active=True).count()
    
    # Get today's stats
    today = datetime.utcnow().date()
    today_stats = db.session.query(
        func.sum(IPUsageSummary.total_queries).label('total_queries'),
        func.count(func.distinct(IPUsageSummary.ip_address)).label('unique_ips')
    ).filter(IPUsageSummary.date == today).first()
    
    return jsonify({
        'top_ips': [
            {
                'ip_address': row.ip_address,
                'total_queries': row.total_queries,
                'unique_sessions': row.unique_sessions,
                'last_activity': row.last_activity.isoformat() if row.last_activity else None
            }
            for row in top_ips
        ],
        'whitelist_count': whitelist_count,
        'today_stats': {
            'total_queries': today_stats.total_queries or 0,
            'unique_ips': today_stats.unique_ips or 0
        }
    })

@app.route('/admin/current-ip', methods=['GET'])
def get_current_ip():
    """Get current user's IP for easy whitelisting"""
    from auth import FreeAccessManager
    
    ip = FreeAccessManager.get_client_ip()
    is_whitelisted, whitelist_entry = FreeAccessManager.is_whitelisted(ip)
    
    return jsonify({
        'ip_address': ip,
        'is_whitelisted': is_whitelisted,
        'whitelist_info': {
            'description': whitelist_entry.description if whitelist_entry else None,
            'created_at': whitelist_entry.created_at.isoformat() if whitelist_entry else None
        } if whitelist_entry else None
    })

# ==================== CONTEXT MANAGEMENT API ENDPOINTS ====================

@app.route('/api/context', methods=['GET'])
def get_context_items():
    """Get all context items for current user"""
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        items = ContextService.get_user_context_items(include_inactive=include_inactive)
        
        return jsonify({
            'success': True,
            'items': [
                {
                    'id': str(item.id),
                    'name': item.name,
                    'description': item.description,
                    'content_type': item.content_type,
                    'token_count': item.token_count,
                    'usage_count': item.usage_count,
                    'created_at': item.created_at.isoformat(),
                    'last_used_at': item.last_used_at.isoformat() if item.last_used_at else None,
                    'is_active': item.is_active,
                    'file_size': item.file_size,
                    'original_filename': item.original_filename
                }
                for item in items
            ]
        })
    except Exception as e:
        app.logger.error(f"Error fetching context items: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch context items'}), 500

@app.route('/api/context', methods=['POST'])
def create_context_item():
    """Create a new context item"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or not data.get('name') or not data.get('content_type'):
            return jsonify({'success': False, 'error': 'Name and content_type are required'}), 400
        
        # Create context item
        context_item = ContextService.create_context_item(
            name=data['name'],
            content_type=data['content_type'],
            content_text=data.get('content_text'),
            description=data.get('description'),
            original_filename=data.get('original_filename'),
            file_path=data.get('file_path'),
            file_size=data.get('file_size'),
            extra_data=data.get('extra_data')
        )
        
        return jsonify({
            'success': True,
            'item': {
                'id': str(context_item.id),
                'name': context_item.name,
                'description': context_item.description,
                'content_type': context_item.content_type,
                'token_count': context_item.token_count,
                'created_at': context_item.created_at.isoformat()
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error creating context item: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to create context item'}), 500

@app.route('/api/context/<item_id>', methods=['GET'])
def get_context_item(item_id):
    """Get specific context item by ID"""
    try:
        item = ContextService.get_context_item(item_id)
        if not item:
            return jsonify({'success': False, 'error': 'Context item not found'}), 404
        
        return jsonify({
            'success': True,
            'item': {
                'id': str(item.id),
                'name': item.name,
                'description': item.description,
                'content_type': item.content_type,
                'content_text': item.content_text,
                'content_summary': item.content_summary,
                'token_count': item.token_count,
                'usage_count': item.usage_count,
                'created_at': item.created_at.isoformat(),
                'updated_at': item.updated_at.isoformat(),
                'last_used_at': item.last_used_at.isoformat() if item.last_used_at else None,
                'is_active': item.is_active,
                'original_filename': item.original_filename,
                'file_path': item.file_path,
                'file_size': item.file_size,
                'extra_data': item.extra_data
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error fetching context item {item_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch context item'}), 500

@app.route('/api/context/<item_id>', methods=['PUT'])
def update_context_item(item_id):
    """Update existing context item"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        updated_item = ContextService.update_context_item(
            item_id=item_id,
            name=data.get('name'),
            description=data.get('description'),
            content_text=data.get('content_text'),
            extra_data=data.get('extra_data')
        )
        
        if not updated_item:
            return jsonify({'success': False, 'error': 'Context item not found'}), 404
        
        return jsonify({
            'success': True,
            'item': {
                'id': str(updated_item.id),
                'name': updated_item.name,
                'description': updated_item.description,
                'content_type': updated_item.content_type,
                'token_count': updated_item.token_count,
                'updated_at': updated_item.updated_at.isoformat()
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error updating context item {item_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to update context item'}), 500

@app.route('/api/context/<item_id>', methods=['DELETE'])
def delete_context_item(item_id):
    """Soft delete context item"""
    try:
        success = ContextService.delete_context_item(item_id)
        if not success:
            return jsonify({'success': False, 'error': 'Context item not found'}), 404
        
        return jsonify({'success': True, 'message': 'Context item deleted'})
    
    except Exception as e:
        app.logger.error(f"Error deleting context item {item_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to delete context item'}), 500

@app.route('/api/context/suggestions', methods=['GET'])
def get_context_suggestions():
    """Get context suggestions based on query text"""
    try:
        query_text = request.args.get('query', '')
        conversation_id = request.args.get('conversation_id')
        limit = int(request.args.get('limit', 5))
        
        if not query_text:
            return jsonify({'success': False, 'error': 'Query text is required'}), 400
        
        suggestions = ContextService.get_context_suggestions(
            query_text=query_text,
            conversation_id=conversation_id,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
    
    except Exception as e:
        app.logger.error(f"Error getting context suggestions: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to get suggestions'}), 500

@app.route('/api/conversation/<conversation_id>/context', methods=['GET'])
def get_conversation_context(conversation_id):
    """Get all active context for a conversation"""
    try:
        context = ContextService.get_conversation_context(conversation_id)
        return jsonify({
            'success': True,
            'context': context
        })
    
    except Exception as e:
        app.logger.error(f"Error fetching conversation context: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch conversation context'}), 500

@app.route('/api/conversation/<conversation_id>/context/<context_item_id>', methods=['POST'])
def add_context_to_conversation(conversation_id, context_item_id):
    """Add context item to conversation"""
    try:
        data = request.get_json() or {}
        relevance_score = float(data.get('relevance_score', 1.0))
        
        context_session = ContextService.add_context_to_conversation(
            conversation_id=conversation_id,
            context_item_id=context_item_id,
            relevance_score=relevance_score
        )
        
        if not context_session:
            return jsonify({'success': False, 'error': 'Context item not found or access denied'}), 404
        
        return jsonify({
            'success': True,
            'session': {
                'id': str(context_session.id),
                'conversation_id': str(context_session.conversation_id),
                'context_item_id': str(context_session.context_item_id),
                'relevance_score': float(context_session.relevance_score),
                'added_at': context_session.added_at.isoformat(),
                'is_active': context_session.is_active
            }
        })
    
    except Exception as e:
        app.logger.error(f"Error adding context to conversation: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to add context to conversation'}), 500

@app.route('/api/conversation/<conversation_id>/context/<context_item_id>', methods=['DELETE'])
def remove_context_from_conversation(conversation_id, context_item_id):
    """Remove context item from conversation"""
    try:
        success = ContextService.remove_context_from_conversation(
            conversation_id=conversation_id,
            context_item_id=context_item_id
        )
        
        if not success:
            return jsonify({'success': False, 'error': 'Context not found in conversation'}), 404
        
        return jsonify({'success': True, 'message': 'Context removed from conversation'})
    
    except Exception as e:
        app.logger.error(f"Error removing context from conversation: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to remove context from conversation'}), 500

@app.route('/api/context/stats', methods=['GET'])
def get_context_stats():
    """Get user context statistics"""
    try:
        stats = ContextService.get_user_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        app.logger.error(f"Error fetching context stats: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch context stats'}), 500

# ==================== END CONTEXT MANAGEMENT API ====================

# ==================== SEARCH API ENDPOINTS ====================

@app.route('/api/search/conversations', methods=['GET'])
def search_conversations():
    """Search conversations by content with project awareness"""
    try:
        query = request.args.get('query', '').strip()
        project_id = request.args.get('project_id')
        limit = int(request.args.get('limit', 20))
        
        if not query:
            return jsonify({'success': False, 'error': 'Query parameter is required'}), 400
        
        from sqlalchemy import or_, and_, exists
        from models import Conversation, Message
        
        # Build search filter using EXISTS for better performance and no DISTINCT issues
        message_exists = exists().where(
            and_(
                Message.conversation_id == Conversation.id,
                Message.content.ilike(f'%{query}%')
            )
        )
        
        search_filter = or_(
            Conversation.title.ilike(f'%{query}%'),
            message_exists
        )
        
        # Build base query with project filter if specified
        base_query = db.session.query(Conversation).filter(search_filter)
        
        if project_id:
            try:
                project_uuid = uuid.UUID(project_id)
                base_query = base_query.filter(Conversation.project_id == project_uuid)
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid project_id'}), 400
        
        # Get conversations ordered by most recent (no DISTINCT needed with EXISTS)
        conversations = base_query.order_by(Conversation.updated_at.desc()).limit(limit).all()
        
        # Format results with matching message snippets
        results = []
        for conv in conversations:
            # Find matching messages in this conversation
            matching_messages = Message.query.filter(
                and_(
                    Message.conversation_id == conv.id,
                    Message.content.ilike(f'%{query}%')
                )
            ).order_by(Message.timestamp.desc()).limit(3).all()
            
            # Create snippets from matching messages
            snippets = []
            for msg in matching_messages:
                content = msg.content
                # Find the query in content and create a snippet around it
                query_lower = query.lower()
                content_lower = content.lower()
                
                if query_lower in content_lower:
                    start_idx = content_lower.find(query_lower)
                    snippet_start = max(0, start_idx - 50)
                    snippet_end = min(len(content), start_idx + len(query) + 50)
                    snippet = content[snippet_start:snippet_end]
                    
                    if snippet_start > 0:
                        snippet = "..." + snippet
                    if snippet_end < len(content):
                        snippet = snippet + "..."
                    
                    snippets.append({
                        'content': snippet,
                        'role': msg.role,
                        'timestamp': msg.timestamp.isoformat()
                    })
            
            # If no message matches but title matches, use title
            if not snippets and query.lower() in conv.title.lower():
                snippets.append({
                    'content': conv.title,
                    'role': 'title',
                    'timestamp': conv.created_at.isoformat()
                })
            
            results.append({
                'id': str(conv.id),
                'title': conv.title,
                'project_id': str(conv.project_id) if conv.project_id else None,
                'created_at': conv.created_at.isoformat(),
                'updated_at': conv.updated_at.isoformat(),
                'tags': conv.tags or [],
                'snippets': snippets[:2]  # Limit to 2 snippets per conversation
            })
        
        return jsonify({
            'success': True,
            'query': query,
            'project_id': project_id,
            'total_results': len(results),
            'conversations': results
        })
        
    except Exception as e:
        app.logger.error(f"Error searching conversations: {str(e)}")
        return jsonify({'success': False, 'error': 'Search failed'}), 500

# ==================== END SEARCH API ====================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)