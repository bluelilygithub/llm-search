# Curam AI Knowledge Base

A comprehensive AI-powered knowledge management and chat application that enables users to interact with multiple Large Language Models (LLMs), manage conversations, upload documents for context, and organize their knowledge through intelligent search and tagging systems with advanced RAG (Retrieval-Augmented Generation) capabilities.

## 🚀 What It Does

Curam AI Knowledge Base is a multi-LLM chat interface that allows users to:

- **Chat with Multiple AI Models**: Interact with OpenAI GPT models (including O1), Anthropic Claude 3.5/4, Google Gemini, Hugging Face models, and Stability AI image/audio generation
- **Advanced RAG Pipeline**: Upload documents and get AI responses enhanced with relevant content from your knowledge base using semantic search and embeddings
- **Multi-User System**: Admin and user roles with separate access controls, user management, and personalized experiences
- **Intelligent Organization**: Tag conversations, organize them into projects, and search through your knowledge base with advanced filtering
- **Real-time Search**: Search conversations by title, content, tags, or project with intelligent filtering and snippets
- **Voice Features**: Text-to-speech for AI responses and speech-to-text for input
- **Model Management**: Enable/disable specific models and manage default model preferences
 - **Project-aware Responses**: Chats automatically include concise project context when a project exists
 - **On‑demand Visuals**: Generate explanatory charts/diagrams for math/statistics answers with one click
 - **Demo Guest Mode**: One‑click “Try the demo” creates a temporary sandbox with clear bannered restrictions
 - **Project‑based Quizzes**: Generate 5 MCQs per project context; subject/year‑aware; stored results and progress summary

## 🏗️ Infrastructure & Technology Stack

### Backend
- **Framework**: Flask 3.0.0 with modular architecture (app.py, config.py, models.py)
- **Database**: PostgreSQL with SQLAlchemy ORM and Flask-Migrate for migrations
- **Authentication**: Multi-user system with admin and regular user roles, session-based auth
- **RAG Pipeline**: OpenAI embeddings with semantic search and document chunking
- **File Processing**: PyPDF2 for PDFs, python-docx for Word documents, BeautifulSoup for URL extraction
- **Rate Limiting**: Flask-Limiter with comprehensive usage tracking
- **CORS**: Flask-CORS for cross-origin requests
- **Storage**: Cloudinary integration for generated image storage

### Frontend
- **UI**: Modern responsive interface with collapsible sidebar, project management, and context panels
- **Styling**: Custom CSS with dark/light theme support and mobile responsiveness
- **Icons**: Font Awesome 6.0.0
- **Charts**: Chart.js for advanced usage analytics and dashboard
- **File Handling**: Drag-and-drop interface with multiple file format support
- **Settings**: Comprehensive settings panel with model configuration and user management

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
- **Text-to-Speech**: Listen to AI responses with speaker button
- **Speech-to-Text**: Voice input capabilities for hands-free interaction

### 🧠 RAG (Retrieval-Augmented Generation) Pipeline
- **Document Processing**: Upload documents (PDF, DOCX, TXT) and automatically generate embeddings
- **Semantic Search**: Find relevant content using OpenAI embeddings and cosine similarity
- **Context Integration**: AI responses enhanced with relevant knowledge base content
- **Visual Indicators**: See which documents were used to generate responses
- **Source Citations**: View document names and relevance scores for transparency
- **User-Specific Knowledge**: Each user's documents are processed and searched independently
- **Stable Implementation**: Document-only RAG for reliable performance (conversation embeddings removed for stability)

### 👥 Multi-User Management System
- **Admin Users**: Full access to all features, user management, and system settings
- **Regular Users**: Access to their own conversations and documents
- **User Roles**: SUPER_ADMIN, ADMIN, USER, VIEWER, GUEST with different permission levels
- **User Management**: Create, edit, and manage user accounts with email validation
- **Profile Management**: Users can update their display names and passwords
- **Access Control**: Conversations and projects are filtered by user ownership

### 📁 Advanced Context Management System
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

### ⚙️ Model Management
- **Model Settings**: Enable/disable specific models for your organization
- **Default Model**: Set preferred default model for new conversations
- **Model Persistence**: Settings saved to database and persist across deployments
- **Model Status**: Track model availability and performance

### 📊 Professional Analytics & Monitoring
- **Comprehensive Usage Tracking**: LLMUsageLog and LLMErrorLog models with detailed metrics
- **Advanced Dashboard**: Chart.js integration with timeline charts, model performance tables
- **Context Analytics**: Track context item usage, token consumption, and effectiveness
- **Real-time Monitoring**: Live dashboard with auto-refresh and export capabilities

### 🔒 Enterprise-Grade Security
- **Multi-layer Authentication**: Multi-user system with role-based access control
- **Input Sanitization**: Comprehensive content sanitization for documents and user inputs
- **CORS & Security Headers**: Proper cross-origin request handling and security configurations
- **Error Handling**: Structured error logging with client-side error reporting
- **Rate Limiting**: Sophisticated rate limiting with usage protections

### 🎨 Modern User Experience
- **Collapsible Sidebar**: Modern sidebar with project navigation and search
- **Responsive Design**: Mobile-first design that works across all devices
- **Settings Panel**: Comprehensive settings with model configuration and user management
- **Account Panel**: User profile management with password updates
- **Export & Import**: Full conversation export with context preservation
- **Personalized Welcome**: Custom welcome messages with user's display name
 - **Icon‑only Project Actions**: Compact project cards with one‑row actions (preview, setup, rename, delete, clone)
 - **Admin Filtering**: Admins can filter Projects/Conversations by user and see owner/user info
 - **Projects Grid (Max 4 Cols)**: Projects grid caps at 4 columns with responsive fallbacks

### 🎯 Education‑ready Math Mode
- **Teacher‑quality Guardrails**: Compute‑first, verify by substitution, explicit self‑correction on contradictions
- **Beginner‑first Teaching**: Default to y = m*x + b for lines, Keep‑Flip‑Change for fraction division, brief definitions for new terms
- **Follow‑ups**: Age‑appropriate comprehension checks, younger‑learner re‑explanations, practical examples (numerically consistent), and extensions
- **Core Math Actions (highlighted)**: Three always‑present follow‑ups are visually accented, plus “Illustrate this response with a explanatory graphic or chart” to add a chart inline
- **Output Style Preference**: Per‑user toggle between plain‑text (ASCII a/b, x^2, sqrt(x)) and rich Markdown/LaTeX output
- **Images/OCR First**: For uploaded images, the assistant transcribes math to plain text before solving; requests one‑line confirmation when unclear
 - **Curriculum Scoping**: Quizzes constrained to NSW topic sets (e.g., Year 10 Core); link surfaced in UI

### 📝 Quizzes & Progress Tracking
- **Subject/Year‑aware Generation**: Quiz prompt respects `project.math_subject` and `math_level` (or user year) with NSW topic hints
- **Anti‑repeat Logic**: Avoids recent stems, shuffles items, and uses expanded subject fallback banks (e.g., Geometry) to guarantee 5 valid MCQs
- **Durable Storage**: `quiz_attempts` and `quiz_answers` tables persist attempts and per‑question results
- **Progress Dashboard**: Latest quiz summary, per‑topic quiz mastery, and now a quiz history list with attempt details
- **Blended Math Signals**: For math topics, quiz correctness contributes to “Signals: + / −” and the topic score
- **APIs**: `POST /projects/<id>/quiz/generate`, `POST /projects/<id>/quiz/submit`, `GET /api/progress/summary`, `GET /api/progress/quiz-history`, `GET /api/progress/quiz-attempt/<attempt_id>`

### 🧮 Mathematics Personas & Seeding (Admin)
- **Seven Core Personas** (category “Mathematics”): Number and Algebra; Functions and Graphs; Measurement and Geometry; Statistics and Probability; Financial Mathematics; Discrete and Modelling; Extension / Pre‑Calculus
- **Create Projects per Persona**: `POST /admin/create_math_projects_for_user` accepts `{ username }` or `{ user_id }`; creates one project per persona (skips duplicates)
- **Seed Subtopic Chats**: `POST /admin/seed_math_subtopics_for_user` accepts `{ username }` or `{ user_id }`; creates one conversation per subtopic with the prompt “Explain what is meant by {subtopic}.” (skips duplicates)
- **Ensure Personas Exist**: `POST /admin/ensure_math_personas` upserts the seven personas under category “Mathematics”

### 🧩 Adaptive Profile (v1)
- **Guest Compatibility**: Adaptive runs only for authenticated users; demo guests are kept simple and capped
- **Auto‑tunes Verbosity**: Lightweight EMA learns from signals like “shorter/tl;dr” or “more detail/step by step” and nudges verbosity (brief/standard/detailed)
- **Respect Explicit Settings**: Adaptive only fills gaps; explicit user preferences win
- **Opt‑in & Reset**: Toggle adaptive profile in Settings and reset the learned score

## 🛠️ Development Setup

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
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

# Run user system migration (if upgrading from older version)
psql -d llm_search_db -f QUICK_MIGRATION.sql

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

# AI Model APIs
OPENAI_API_KEY=your_openai_key
CLAUDE_API_KEY=your_claude_key  
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
├── app.py                    # Main Flask application with 4000+ lines of endpoints
├── config.py                 # Multi-environment configuration
├── models.py                 # Database models (20+ models including user management)
├── auth.py                   # Multi-user authentication system
├── llm_service.py           # LLMService with 20+ model integrations
├── rag_service_simple.py    # RAG pipeline with embeddings and semantic search
├── security_utils.py        # Security utilities and access control
├── user_models.py           # User management models
├── database.py              # Database initialization and utilities
├── logger.py                # Structured logging configuration
├── requirements.txt         # Python dependencies (20+ packages)
├── Procfile                 # Production deployment configuration
├── templates/
│   ├── app_main.html       # Main application UI
│   ├── login.html          # Authentication interface
│   ├── components/         # Reusable UI components
│   └── modals/             # Modal dialogs
└── static/
    ├── css/style.css       # Application styling
    ├── js/app.js          # Frontend JavaScript (8000+ lines)
    └── images/            # Static assets
```

### Key API Endpoints

#### Chat & Conversations
- `POST /chat` - Multi-LLM chat with RAG context injection
- `GET/POST /conversations` - Conversation CRUD with user filtering  
- `GET/POST /conversations/<id>/messages` - Message management
- `POST /conversations/<id>/attachments` - File upload handling
 - `DELETE /conversations/<id>` - Delete a conversation (CSRF‑exempt)
 - `POST /auth/guest-login` - Create and sign into a time‑limited demo guest (DEMO_MODE)

#### RAG Pipeline
- `POST /api/rag/process-document` - Process single document for embeddings
- `POST /api/rag/process-all` - Process all documents for current user
- `POST /api/rag/search` - Semantic search across knowledge base
- `POST /api/rag/get-context` - Get relevant context for AI responses

#### User Management
- `GET/POST /api/users` - User CRUD operations (admin only)
- `PUT /api/users/<id>` - Update user information
- `DELETE /api/users/<id>` - Delete user account
- `PUT /api/users/update-profile` - Update own profile (display name, password)

#### Model Management
- `GET/POST /api/model-settings` - Manage enabled/disabled models
- `GET /api/models` - Get available models with status

#### Context Management
- `GET/POST /api/context` - Context item management
- `GET /api/context/<item_id>` - Individual context item operations
- `GET /api/context/suggestions` - AI-powered context suggestions
- `POST/DELETE /api/conversation/<id>/context/<item_id>` - Context-conversation linking

#### Advanced Features
- `POST /upload-context` - Document processing with task types
- `POST /extract-url` - URL content extraction with BeautifulSoup
- `POST /stability-edit-image` - Stability AI image editing
- `POST /transcribe` - Google Speech-to-Text integration
 - `POST /api/visualize` - Generate an explanatory chart/diagram from the latest answer (returns base64 PNG)
- `POST /projects/<project_id>/quiz/generate` - Subject/year‑aware quiz generation (5 MCQs)
- `POST /projects/<project_id>/quiz/submit` - Persist attempt + answers; returns score
- `GET /api/progress/quiz-history` - Attempt list + stats; filters by window
- `GET /api/progress/quiz-attempt/<attempt_id>` - Full attempt detail
 - `POST /auth/logout` - CSRF‑exempt; when DEMO_PURGE_ON_LOGOUT=true and user is a demo guest, purge the user and sandbox on logout

#### Search & Organization
- `GET /api/search/conversations` - Advanced search with snippets
- `GET/POST/DELETE /api/conversations/<id>/tags` - Tag management
- `GET/POST /projects` - Project organization system
 - `POST /projects/<project_id>/clone` - Clone a project (copies template/settings; excludes conversations)

#### Analytics & Monitoring  
- `GET /llm-usage-stats` - Comprehensive usage analytics
- `GET /monthly-token-usage` - Time-series usage data
- `GET /llm-error-log` - Error tracking and monitoring

### Database Models

#### Core Models
- **Conversation**: Enhanced with user_id for multi-user support
- **Message**: Core chat messages with UUID primary keys
- **Project**: Organization system for conversations with owner_id
- **Attachment**: File upload tracking

#### User Management
- **User**: User accounts with roles, status, and profile information
- **UserRole**: Role definitions (SUPER_ADMIN, ADMIN, USER, VIEWER, GUEST)
- **UserStatus**: User status tracking (ACTIVE, INACTIVE, SUSPENDED)
- **UserAuditLog**: Audit trail for user actions

#### RAG Pipeline
- **ContextItem**: Document storage with content extraction
- **ModelSettings**: Model configuration and status tracking

#### Analytics & Monitoring
- **LLMUsageLog/LLMErrorLog**: Model usage and error tracking
- **ContextUsageLog**: Context item usage tracking
#### Assessment
- **quiz_attempts**: user_id, project_id, score, correct, total_questions, time_taken_seconds, created_at
- **quiz_answers**: attempt_id, question_number, topic, question_text, student_answer, correct_answer, is_correct, created_at

## 🚀 Recent Updates

### RAG Implementation (Current)
- **Document Processing**: Automatic embedding generation for uploaded documents
- **Semantic Search**: Find relevant content using OpenAI embeddings
- **Context Integration**: AI responses enhanced with knowledge base content
- **Visual Indicators**: See which documents informed each response
- **User-Specific**: Each user's documents are processed independently

### RAG Enhancement Attempt (October 2025)
**Status**: Unsuccessful - Rolled back to stable version

We attempted to enhance the RAG system with the following features:
- **Conversation Embeddings**: Generate embeddings for conversation summaries
- **Message Embeddings**: Create embeddings for individual messages
- **Cross-Source Search**: Search across documents, conversations, and messages
- **Vector Database Integration**: Implement pgvector for PostgreSQL

**Challenges Encountered**:
- Railway PostgreSQL doesn't support pgvector extension
- JSONB-based vector storage proved complex and unreliable
- Database migration issues with vector columns
- Performance degradation with large datasets

**Decision**: Rolled back to the stable document-only RAG implementation that provides reliable semantic search across uploaded documents without the complexity of conversation/message embeddings.

**Current RAG Capabilities**:
- ✅ Document processing and embedding generation
- ✅ Semantic search across knowledge base
- ✅ Context injection into AI responses
- ✅ Source citations and relevance scoring
- ❌ Conversation/message embeddings (removed for stability)

### Multi-User System
- **User Management**: Admin can create and manage user accounts
- **Role-Based Access**: Different permission levels for different user types
- **Profile Management**: Users can update their own information
- **Access Control**: Conversations and projects filtered by user ownership

### Model Management
- **Model Settings**: Enable/disable specific models
- **Default Model**: Set preferred model for new conversations
- **Database Persistence**: Settings saved and persist across deployments

### UI/UX Improvements
- **Account Panel**: Simplified user profile management
- **Settings Reorganization**: Better organization of settings options
- **Visual Indicators**: RAG sources displayed in chat responses
- **Personalized Experience**: Custom welcome messages and user-specific content
- **Project Cloning**: One‑click clone for projects without copying conversations
- **Speech Input Resilience**: Web Speech improvements (interim results, one retry on `no-speech`, clearer UI states)
 - **Always‑on Project Context**: System prompt includes project name/description and key fields to avoid “no access” disclaimers
 - **Math Follow‑ups Styling**: Core math actions highlighted with a complementary color; dynamic suggestions remain neutral
 - **On‑demand Illustration**: One‑click button adds a chart/graphic below the assistant message
 - **Demo Banner & Restrictions**: Visible banner for demo guests (expiry, allowed vs. restricted actions), admin‑only UI hidden
 - **Curriculum Sources Tooltip**: Adds NSW references (e.g., Class Mathematics Year 10 Core) in assistant message info
 - **Admin Personas Panel**: Personas appear grouped under category; mathematics personas show under “Mathematics”

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 📞 Support

For support, email support@example.com or create an issue in the GitHub repository.