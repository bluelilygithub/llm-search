# AI Knowledge Base

A comprehensive AI-powered knowledge management and chat application that enables users to interact with multiple Large Language Models (LLMs), manage conversations, upload documents for context, and organize their knowledge through intelligent search and tagging systems.

## 🚀 What It Does

The AI Knowledge Base is a multi-LLM chat interface that allows users to:

- **Chat with Multiple AI Models**: Interact with OpenAI GPT models, Anthropic Claude, Google Gemini, and Hugging Face models
- **Document Upload & Context Management**: Upload documents (PDF, DOCX, TXT) and use them as context for AI conversations
- **Intelligent Organization**: Tag conversations, organize them into projects, and search through your knowledge base
- **Free & Authenticated Access**: Supports both free-tier users and authenticated users with separate conversation histories
- **Real-time Search**: Search conversations by title, content, or tags with intelligent filtering

## 🏗️ Infrastructure & Technology Stack

### Backend
- **Framework**: Flask (Python web framework)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: Simple session-based authentication with IP whitelisting
- **File Processing**: PyPDF2 for PDFs, python-docx for Word documents
- **Rate Limiting**: Flask-Limiter for API protection
- **CORS**: Flask-CORS for cross-origin requests

### Frontend
- **UI**: Vanilla JavaScript with HTML5/CSS3
- **Styling**: Custom CSS with responsive design
- **Icons**: Font Awesome
- **Charts**: Chart.js for usage analytics
- **File Handling**: Drag-and-drop interface with progress tracking

### LLM Integration
- **OpenAI**: GPT-3.5, GPT-4, GPT-4 Turbo, GPT-4o, O1 models
- **Anthropic**: Claude 3.5 Sonnet, Claude 3 Opus/Sonnet/Haiku
- **Google**: Gemini Pro and Gemini Flash
- **Hugging Face**: Llama 2, Mixtral, CodeLlama models

### Deployment
- **Containerization**: Docker support
- **Process Management**: Gunicorn WSGI server
- **Environment**: Railway/Cloud platform ready
- **Logging**: Structured logging with rotation

## ✨ Current Features

### 🤖 Multi-LLM Chat Interface
- Switch between different AI models mid-conversation
- Real-time streaming responses
- Message history and conversation continuity
- Model-specific pricing and token tracking

### 📁 Document Management & Context System
- Upload multiple file formats (PDF, DOCX, TXT, CSV)
- Document processing with content extraction
- Context panel for active document management
- Intelligent context injection into conversations

### 🏷️ Organization & Search
- **Tagging System**: Tag conversations with custom labels
- **Project Organization**: Group conversations into projects
- **Smart Search**: Search by conversation title, message content, or tags
- **Real-time Filtering**: Client-side filtering with visual highlighting

### 👥 User Management
- **Free Tier**: Anonymous users with session-based conversation tracking
- **Authenticated Users**: Persistent conversation history across sessions
- **Complete Separation**: Free and authenticated user conversations are isolated
- **Rate Limiting**: Configurable query limits for free users

### 📊 Analytics & Monitoring
- **Usage Tracking**: Monitor API calls, costs, and model usage
- **Error Logging**: Comprehensive error tracking and reporting
- **Admin Dashboard**: User management and system monitoring
- **IP Whitelisting**: Advanced access control for enterprise use

### 🔒 Security Features
- Session-based authentication with secure cookies
- IP-based rate limiting and tracking
- CORS protection and secure headers
- Input sanitization and XSS protection

### 🎨 User Experience
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Dark/Light Theme**: Automatic theme detection
- **Keyboard Shortcuts**: Quick navigation and actions
- **Progress Indicators**: Visual feedback for uploads and processing
- **Export Functionality**: Export conversations to Markdown

## 🎯 Five Priority UI Features for Next Implementation

### 1. **Advanced Search & Filters Interface**
```
Priority: High | Effort: Medium
```
- **Advanced Search Modal**: Date ranges, model filters, project filtering
- **Saved Search Queries**: Bookmark frequently used search combinations  
- **Search History**: Quick access to recent searches
- **Filter Chips**: Visual filter indicators with easy removal
- **Search Suggestions**: Auto-complete based on existing tags and content

### 2. **Conversation Management Dashboard**
```
Priority: High | Effort: Medium
```
- **Conversation Overview**: Grid/list view toggle with thumbnails
- **Bulk Operations**: Select multiple conversations for tagging, deletion, or export
- **Conversation Stats**: Token usage, model distribution, creation dates
- **Favorites System**: Star important conversations for quick access
- **Archive/Unarchive**: Hide old conversations without deletion

### 3. **Enhanced Context & Document Workspace**
```
Priority: Medium | Effort: High
```
- **Document Preview**: In-app PDF/document viewer with highlights
- **Context Templates**: Pre-built context sets for different use cases
- **Document Versioning**: Track changes to uploaded documents
- **Collaborative Context**: Share document sets between authenticated users
- **Smart Context Suggestions**: AI-powered recommendations for relevant documents

### 4. **Real-time Collaboration Features**
```
Priority: Medium | Effort: High  
```
- **Shared Conversations**: Invite others to view/contribute to conversations
- **Comment System**: Add notes and annotations to specific messages
- **Conversation Branching**: Fork conversations to explore different paths
- **Team Workspaces**: Shared project spaces for organizations
- **Activity Feeds**: See recent activity across shared conversations

### 5. **Advanced Customization & Personalization**
```
Priority: Low | Effort: Medium
```
- **Custom Themes**: User-selectable color schemes and layouts
- **Personalized Dashboards**: Drag-and-drop widget arrangement
- **Custom Shortcuts**: User-defined keyboard shortcuts and quick actions
- **Model Presets**: Save preferred model settings and system prompts
- **Notification Preferences**: Configurable alerts for various events

## 🛠️ Development Setup

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
- Node.js (for frontend asset management, optional)

### Installation
```bash
# Clone repository
git clone <repository-url>
cd ai-knowledge-base

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your API keys and database URL

# Run database migrations
python -c "from app import db; db.create_all()"
psql -d your_database -f migration_add_user_columns.sql

# Start development server
python app.py
```

### Environment Variables
```bash
DATABASE_URL=postgresql://user:password@localhost/dbname
OPENAI_API_KEY=your_openai_key
CLAUDE_API_KEY=your_claude_key  
GEMINI_API_KEY=your_gemini_key
HUGGING_FACE_API_KEY=your_hf_key
FLASK_SECRET_KEY=your_secret_key
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 📞 Support

For support, email support@example.com or create an issue in the GitHub repository.