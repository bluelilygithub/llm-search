from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
import uuid
from datetime import datetime
from flask_migrate import Migrate
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

app = Flask(__name__, static_folder='static')
app.config.from_object(Config)

# Security configurations
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

db = SQLAlchemy(app)
CORS(app)

# Rate limiting - use in-memory for simplicity
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"]
)
limiter.init_app(app)

from models import Conversation, Message, Attachment, Project
from llm_service import LLMService

llm_service = LLMService()

migrate = Migrate(app, db)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'message': 'AI Knowledge Base API is running'})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/init-db')
def init_database():
    try:
        db.create_all()
        return jsonify({'message': 'Database initialized successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/projects', methods=['GET'])
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
def chat():
    try:
        data = request.get_json()
        
        if not data or not data.get('message') or not data.get('model'):
            return jsonify({'error': 'Message and model are required'}), 400
        
        conversation_id = data.get('conversation_id')
        user_message = data['message']
        model = data['model']
        
        print(f"Chat request: model={model}, message={user_message[:50]}...")
        
        # Get conversation history if conversation exists
        messages = []
        if conversation_id:
            conv_uuid = uuid.UUID(conversation_id)
            conversation = Conversation.query.get_or_404(conv_uuid)
            db_messages = Message.query.filter_by(conversation_id=conv_uuid).order_by(Message.timestamp.asc()).all()
            messages = llm_service.format_conversation_for_llm(db_messages)
            # Add context document(s) to prompt if present
            import json
            docs = getattr(conversation, 'context_documents', None)
            # Debug logging removed for security
            if isinstance(docs, str):
                try:
                    docs = json.loads(docs)
                except Exception:
                    docs = []
            if docs:
                for doc in docs:
                    if doc and 'content' in doc:
                        task_type = doc.get('task_type', 'instructions')
                        filename = doc.get('filename', 'uploaded file')
                        content = doc['content']
                        
                        # Create context-aware system message
                        if task_type == 'summary':
                            system_msg = f"You have been provided with a document ({filename}) to summarize. You can analyze, count words, and provide detailed summaries of this content:\n\n{content}"
                        elif task_type == 'analysis':
                            system_msg = f"You have been provided with a document ({filename}) to analyze. You can examine, count words, and provide detailed analysis of this content:\n\n{content}"
                        else:
                            system_msg = f"Document reference ({filename}): You have access to this document content and can answer questions about it, count words, analyze it, or use it as guidelines:\n\n{content}"
                        
                        messages.insert(0, {
                            'role': 'system',
                            'content': system_msg  # Full document content
                        })
        # Debug: print the full prompt
        print("\n--- LLM PROMPT MESSAGES ---")
        for idx, m in enumerate(messages):
            print(f"{idx}. {m['role']}: {m['content'][:300].replace(chr(10), ' ')}{' ...' if len(m['content']) > 300 else ''}")
        print("--- END PROMPT ---\n")
        
        # Add current user message
        messages.append({'role': 'user', 'content': user_message})
        
        print(f"Calling LLM service...")
        # Get AI response and usage info
        ai_response, tokens, estimated_cost = llm_service.get_response(model, messages)
        print(f"Got response: {ai_response[:50]}...")
        # Log usage
        from models import LLMUsageLog
        usage_log = LLMUsageLog(
            model=model,
            conversation_id=conversation_id if conversation_id else None,
            tokens=tokens,
            estimated_cost=estimated_cost
        )
        db.session.add(usage_log)
        db.session.commit()
        
        return jsonify({
            'response': ai_response,
            'model': model,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        print(f"Chat error: {str(e)}")
        # Log error
        from models import LLMErrorLog
        error_log = LLMErrorLog(
            model=model,
            conversation_id=conversation_id if 'conversation_id' in locals() and conversation_id else None,
            error_message=str(e)
        )
        db.session.add(error_log)
        db.session.commit()
        # Remove any reference to error_msg variable
        return jsonify({'error': str(e)}), 500

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']
        print('Received file:', audio_file.filename, 'Content-Type:', audio_file.content_type)
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
        print(f"Transcription error: {str(e)}")
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
        print(f"Attachment upload error: {e}")
        import traceback; traceback.print_exc()
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
        
        # File logging removed for security
        # Content logging removed for security
        
        import json
        docs = conversation.context_documents
        # Context logging removed for security
        
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
        # Context update logging removed for security
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
        print(f"Context extraction error: {e}")
        import traceback; traceback.print_exc()
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
        print(f"URL extraction error: {e}")
        import traceback; traceback.print_exc()
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)