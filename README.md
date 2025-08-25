# AI Knowledge Base

A comprehensive AI-powered knowledge management and chat application that enables users to interact with multiple Large Language Models (LLMs), manage conversations, upload documents for context, and organize their knowledge through intelligent search and tagging systems.

## 🚀 What It Does

The AI Knowledge Base is a multi-LLM chat interface that allows users to:

- **Chat with Multiple AI Models**: Interact with OpenAI GPT models (including O1), Anthropic Claude 3.5/4, Google Gemini, Hugging Face models, and Stability AI image/audio generation
- **Advanced Context Management**: Upload documents (PDF, DOCX, TXT, CSV), extract content from URLs, and manage context items across conversations with the new Context Service
- **Intelligent Organization**: Tag conversations, organize them into projects, and search through your knowledge base with advanced filtering
- **Dual Access System**: Robust free-tier access with IP tracking/whitelisting and authenticated users with unlimited access
- **Real-time Search**: Search conversations by title, content, tags, or project with intelligent filtering and snippets
- **Image & Audio Generation**: Create and edit images using Stability AI models, with Cloudinary integration for storage

## 🏗️ Infrastructure & Technology Stack

### Backend
- **Framework**: Flask 3.0.0 with modular architecture (app.py, config.py, models.py)
- **Database**: PostgreSQL with SQLAlchemy ORM and Flask-Migrate for migrations
- **Authentication**: SimpleAuth system with IP whitelisting, session-based auth, and dual access modes
- **File Processing**: PyPDF2 for PDFs, python-docx for Word documents, BeautifulSoup for URL extraction
- **Rate Limiting**: Flask-Limiter with comprehensive free-tier tracking
- **CORS**: Flask-CORS for cross-origin requests
- **Context Management**: New ContextService with advanced context item management
- **Storage**: Cloudinary integration for generated image storage

### Frontend
- **UI**: Modern responsive interface with collapsible sidebar, project management, and context panels
- **Styling**: Custom CSS with dark/light theme support and mobile responsiveness
- **Icons**: Font Awesome 6.0.0
- **Charts**: Chart.js for advanced usage analytics and dashboard
- **File Handling**: Drag-and-drop interface with multiple file format support
- **Settings**: Comprehensive settings panel with model configuration and access checking

### LLM Integration
- **OpenAI**: GPT-3.5, GPT-4, GPT-4 Turbo, GPT-4o/4o-mini, O1-preview/mini models with updated pricing
- **Anthropic**: Claude 3.5 Sonnet, Claude 4 Sonnet, Claude 3 Opus/Sonnet/Haiku with direct HTTP requests
- **Google**: Gemini 1.5 Pro/Flash with updated model mappings
- **Hugging Face**: Llama 2 70B, Mixtral 8x7B, CodeLlama 34B via Inference API
- **Stability AI**: Image generation (Ultra, Core, SD3) and Audio generation with advanced editing capabilities

### Deployment
- **Cloud Ready**: Gunicorn WSGI server with Procfile for Railway/Heroku deployment
- **Environment**: Multi-environment configuration (development, production, testing)
- **Logging**: Structured logging with RotatingFileHandler and service-specific loggers
- **Database Migrations**: SQL migration scripts and Flask-Migrate support

## ✨ Current Features

### 🤖 Advanced Multi-LLM Chat Interface
- Switch between 20+ different AI models including latest O1 and Claude 4 models
- Real-time streaming responses with proper error handling
- Message history and conversation continuity with user identification
- Model-specific pricing, token tracking, and usage analytics
- **New**: Image editing capabilities with Stability AI (remove background, search & replace, recoloring)

### 📁 Advanced Context Management System
- **Context Service**: New centralized context management with ContextItem, ContextSession, and usage tracking
- Upload multiple file formats (PDF, DOCX, TXT, CSV) with content extraction and sanitization
- **URL Content Extraction**: Extract and process content from web URLs with BeautifulSoup
- Context panel with search, statistics, and conversation-specific context management
- Smart context suggestions based on query text and usage patterns
- Context templates and analytics for power users

### 🏷️ Enhanced Organization & Search
- **Advanced Tagging System**: Full CRUD operations for tags with search and filtering
- **Project Management**: Complete project system with creation, deletion, and conversation assignment
- **Powerful Search API**: Backend search with conversation content, snippets, and project filtering
- **Real-time Filtering**: Client-side and server-side search with visual highlighting

### 👥 Robust User Management & Access Control
- **Dual Access System**: SimpleAuth class with sophisticated free-tier and authenticated modes
- **IP Whitelisting**: Dynamic IP management with admin controls and usage tracking
- **Free Tier Tracking**: Multi-method tracking (session, IP, hash) with comprehensive logging
- **Rate Limiting**: Advanced Flask-Limiter configuration with model-specific limits
- **Admin Interface**: Full admin panel with whitelist management and usage statistics

### 📊 Professional Analytics & Monitoring
- **Comprehensive Usage Tracking**: LLMUsageLog and LLMErrorLog models with detailed metrics
- **Advanced Dashboard**: Chart.js integration with timeline charts, model performance tables
- **Context Analytics**: Track context item usage, token consumption, and effectiveness
- **Real-time Monitoring**: Live dashboard with auto-refresh and export capabilities
- **Free Access Analytics**: Detailed tracking of free tier usage with IP analytics

### 🔒 Enterprise-Grade Security
- **Multi-layer Authentication**: SimpleAuth system with session-based and IP-based controls
- **Input Sanitization**: Comprehensive content sanitization for documents and user inputs
- **CORS & Security Headers**: Proper cross-origin request handling and security configurations
- **Error Handling**: Structured error logging with client-side error reporting
- **Rate Limiting**: Sophisticated rate limiting with free tier protections

### 🎨 Modern User Experience
- **Collapsible Sidebar**: Modern sidebar with project navigation and search
- **Responsive Design**: Mobile-first design that works across all devices
- **Settings Panel**: Comprehensive settings with model configuration and access checking
- **Context Panel**: Advanced context management UI with drag-and-drop support
- **Export & Import**: Full conversation export with context preservation
- **Voice Input**: Voice recording capabilities with Google Speech-to-Text integration

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
- PostgreSQL 12+ (with vector extension support for future features)
- Node.js (optional, for frontend development tools)

### Installation
```bash
# Clone repository
git clone <repository-url>
cd llm-search

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your API keys and database URL (see Environment Variables section)

# Setup PostgreSQL database
createdb llm_search_db  # or use your preferred database name

# Run database migrations
python -c "from app import db; db.create_all()"
psql -d llm_search_db -f migration_add_user_columns.sql

# Initialize database with extensions (optional for advanced features)
python -c "from database import init_database; from app import app; init_database(app)"

# Test database connection
python -c "from database import test_connection; from app import app; test_connection(app)"

# Start development server
python app.py
```

### Production Deployment
```bash
# For Railway, Heroku, or similar platforms
# Procfile is included for web: gunicorn app:app

# Environment-specific configuration
export FLASK_CONFIG=production
export FLASK_DEBUG=False

# Database migrations in production
flask db init  # First time only
flask db migrate -m "Initial migration"
flask db upgrade
```

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/dbname
DB_POOL_SIZE=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
DB_MAX_OVERFLOW=20

# AI Model APIs
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_claude_key  
GEMINI_API_KEY=your_gemini_key
HUGGING_FACE_API_KEY=your_hf_key
STABILITY_API_KEY=your_stability_key

# Authentication & Security
SECRET_KEY=your_secret_key_minimum_32_characters_long_random_string
AUTH_PASSWORD=your_admin_password_or_use_generate_password_hash

# Cloud Storage (Optional)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Configuration
FLASK_CONFIG=production  # or development, testing
FLASK_DEBUG=False
```

## 🏛️ Architecture Overview

### Core Application Structure
```
llm-search/
├── app.py                    # Main Flask application with 1900+ lines of endpoints
├── config.py                 # Multi-environment configuration
├── models.py                 # Database models (19+ models including context management)
├── auth.py                   # SimpleAuth system with FreeAccessManager
├── llm_service.py           # LLMService with 20+ model integrations
├── context_service.py       # New ContextService for advanced context management  
├── database.py              # Database initialization and utilities
├── logger.py                # Structured logging configuration
├── migration_add_user_columns.sql  # Database migration scripts
├── requirements.txt         # Python dependencies (17 packages)
├── Procfile                 # Production deployment configuration
├── templates/
│   ├── index.html          # Main application UI (1330+ lines)
│   └── login.html          # Authentication interface
└── static/
    ├── css/style.css       # Application styling
    ├── js/app.js          # Frontend JavaScript (68+ functions)
    └── images/            # Static assets
```

### Key API Endpoints

#### Chat & Conversations
- `POST /chat` - Multi-LLM chat with context injection
- `GET/POST /conversations` - Conversation CRUD with user filtering  
- `GET/POST /conversations/<id>/messages` - Message management
- `POST /conversations/<id>/attachments` - File upload handling

#### Context Management (New)
- `GET/POST /api/context` - Context item management
- `GET /api/context/<item_id>` - Individual context item operations
- `GET /api/context/suggestions` - AI-powered context suggestions
- `POST/DELETE /api/conversation/<id>/context/<item_id>` - Context-conversation linking

#### Advanced Features
- `POST /upload-context` - Document processing with task types
- `POST /extract-url` - URL content extraction with BeautifulSoup
- `POST /stability-edit-image` - Stability AI image editing
- `POST /transcribe` - Google Speech-to-Text integration

#### Search & Organization
- `GET /api/search/conversations` - Advanced search with snippets
- `GET/POST/DELETE /api/conversations/<id>/tags` - Tag management
- `GET/POST /projects` - Project organization system

#### Analytics & Monitoring  
- `GET /llm-usage-stats` - Comprehensive usage analytics
- `GET /monthly-token-usage` - Time-series usage data
- `GET /llm-error-log` - Error tracking and monitoring

#### Administration
- `GET/POST/DELETE /admin/whitelist` - IP whitelist management
- `GET /admin/usage-stats` - Free tier usage analytics
- `GET /admin/current-ip` - IP identification utilities

### Database Models

#### Core Models
- **Conversation**: Enhanced with user_id, session_id, ip_address for dual access
- **Message**: Core chat messages with UUID primary keys
- **Project**: Organization system for conversations
- **Attachment**: File upload tracking

#### Context Management (New)
- **ContextItem**: Centralized context storage with analytics
- **ContextSession**: Context-conversation relationships
- **ContextUsageLog**: Detailed usage tracking
- **ContextTemplate**: Reusable context sets

#### Access Control & Analytics
- **FreeAccessLog**: Comprehensive free tier tracking
- **IPWhitelist**: Dynamic IP management
- **IPUsageSummary**: Daily usage aggregation
- **LLMUsageLog/LLMErrorLog**: Model usage and error tracking

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## ⚠️ CURRENT ISSUES & KNOWN PROBLEMS

### 🚨 **Analytics Dashboard Issues**
**Status**: BROKEN - Charts not displaying  
**Affected Components**: Usage Stats and Activity Timeline charts  
**Root Cause**: Frontend/Backend integration conflicts during recent analytics enhancement attempts

#### **Specific Problems:**

1. **Charts Not Rendering** ❌
   - **Issue**: Canvas elements exist but charts don't display
   - **Location**: `/templates/index.html` - Usage Metrics and Activity Timeline widgets
   - **Cause**: `updateDashboardData()` function conflicts with Chart.js initialization
   - **Evidence**: Chart.js code exists in `app.js:1820-1870` but charts remain blank

2. **Time Range Filtering Broken** ❌ 
   - **Issue**: Dropdown changes cause "Loading data..." indefinitely
   - **Location**: Dashboard time range selector triggers `updateDashboardTimeRange()`
   - **Cause**: Function calls disabled/broken during API integration attempts

3. **IP Whitelist Management Partially Working** ⚠️
   - **Working**: Button shows/hides IP whitelist content
   - **Broken**: Table shows "Loading data..." - tries to fetch from `/api/ip-whitelist` (doesn't exist)
   - **Location**: `populateWhitelistTable()` function in HTML

#### **Technical Debt Created:**
- **Dual Function Systems**: Both `app.js` and `templates/index.html` have competing dashboard functions
- **API Endpoint Mismatch**: Frontend calls `/api/*` endpoints that were partially implemented then removed
- **Function Call Conflicts**: `openSettingsModal()` in app.js calls `updateDashboardData()` which overwrites Chart.js canvases

#### **What Was Working Before:**
- Chart.js charts displaying usage statistics
- Basic dashboard functionality  
- Time filtering with sample data

#### **Recent Changes That Broke It:**
1. **Commit fa5c6fe**: "Implement complete real API backend" - Added API endpoints but created conflicts
2. **Commit 46b85bc**: "Resolve analytics dashboard remaining issues" - Broke chart rendering
3. **Multiple Reverts**: Created inconsistent state between frontend and backend expectations

### 🔧 **Quick Fix Recommendations:**

#### **Option 1: Restore Original Charts (Recommended)**
1. Identify last commit where charts were working (before analytics changes)
2. Cherry-pick just the chart rendering code
3. Remove all `updateDashboardData()` calls that overwrite canvases

#### **Option 2: Complete the API Integration**  
1. Implement missing `/api/ip-whitelist`, `/api/usage-stats`, `/api/activity-log` endpoints
2. Fix frontend to properly handle API responses
3. Add proper error handling for API failures

#### **Option 3: Revert to Sample Data**
1. Remove API calls completely
2. Use static/sample data for dashboard
3. Focus on chart rendering functionality

### 🔍 **Debugging Steps Taken:**
- ✅ Identified canvas elements exist in HTML
- ✅ Confirmed Chart.js code exists in app.js  
- ✅ Found function conflicts between app.js and HTML
- ❌ Unable to restore chart rendering functionality
- ❌ Time filtering still triggers infinite loading states

### 📋 **Files Needing Attention:**
- `static/js/app.js` - Chart rendering functions (lines 1811-1900+)
- `templates/index.html` - Dashboard functions and `updateDashboardData()`
- Analytics modal HTML structure may need alignment with Chart.js expectations

---

## 📞 Support

For support, email support@example.com or create an issue in the GitHub repository.

**Note**: The analytics dashboard issues are currently under investigation. All other application features (chat, context management, search, projects) remain fully functional.