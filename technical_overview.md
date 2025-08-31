# Technical Architecture & System Operation

## **1. Overall Architecture**
Your system follows a **Flask-based web application architecture** with a **modular service-oriented design**:

```
Frontend (HTML/CSS/JS) ↔ Flask App (app.py) ↔ Services ↔ Database (PostgreSQL)
                                    ↓
                            External AI APIs
```

## **2. Core System Components**

### **Web Server Layer**
- **Flask 3.0.0** as the main web framework
- **Gunicorn** WSGI server for production deployment on Railway
- **CSRF protection** and **rate limiting** for security
- **CORS support** for cross-origin requests

### **Service Layer**
- **LLMService**: Manages all AI model interactions (OpenAI, Claude, Gemini, etc.)
- **ContextService**: Handles document uploads, processing, and context management
- **Auth System**: Dual access control (free tier + authenticated users)

### **Data Layer**
- **PostgreSQL** database with SQLAlchemy ORM
- **Connection pooling** for production performance
- **Migration system** for database schema updates

## **3. How the System Functions**

### **Request Flow**
1. **User Request** → Flask route handler
2. **Authentication Check** → FreeAccessManager or session validation
3. **Service Layer** → LLMService/ContextService as needed
4. **External API Calls** → OpenAI, Claude, Gemini, etc.
5. **Response Processing** → Format and return to user

### **Key Operational Patterns**

**Chat System:**
```
User Input → Route /chat → LLMService.get_response() → AI API → Store in Database → Return Response
```

**Document Processing:**
```
File Upload → Route /upload-context → ContextService.create_context_item() → Store in Database → Available for AI Context
```

**Context Injection:**
```
Chat Request → Load Relevant Context → Inject into AI Prompt → Get AI Response → Log Usage
```

## **4. Railway Deployment Architecture**

### **Production Setup**
- **Environment-based configuration** (development/production/testing)
- **Database connection pooling** optimized for Railway's PostgreSQL
- **Static file serving** through Flask
- **Health check endpoint** (`/health`) for monitoring

### **Environment Variables**
- **API Keys**: OpenAI, Claude, Gemini, Hugging Face, Stability AI
- **Database**: `DATABASE_URL` from Railway
- **Security**: `SECRET_KEY`, `AUTH_PASSWORD`
- **Configuration**: `FLASK_CONFIG=production`

## **5. Data Flow & State Management**

### **User Sessions**
- **Free Users**: Session-based tracking with IP monitoring
- **Authenticated Users**: User ID-based access control
- **Hybrid Tracking**: Multiple methods for free tier usage limits

### **Context Management**
- **Document Storage**: Files processed and stored as searchable text
- **Context Linking**: Documents can be attached to specific conversations
- **Smart Suggestions**: AI-powered context recommendations

### **Conversation Persistence**
- **Message History**: All chat interactions stored in database
- **Project Organization**: Conversations grouped into projects
- **Tagging System**: Flexible categorization of conversations

## **6. External Integrations**

### **AI Model APIs**
- **OpenAI**: GPT models, O1, image generation
- **Anthropic**: Claude models via direct HTTP
- **Google**: Gemini models
- **Hugging Face**: Open-source models
- **Stability AI**: Image/audio generation

### **File Processing**
- **PDF**: PyPDF2 for text extraction
- **Word**: python-docx for document processing
- **Web Scraping**: BeautifulSoup for URL content extraction
- **Image Processing**: Cloudinary integration for storage

## **7. Security & Access Control**

### **Multi-Layer Security**
- **CSRF Protection**: Token-based request validation
- **Rate Limiting**: Flask-Limiter with model-specific limits
- **Input Sanitization**: HTML escaping and content validation
- **IP Whitelisting**: Admin-controlled access management

### **Access Tiers**
- **Free Tier**: 10 queries per 24 hours with IP tracking
- **Whitelisted**: Unlimited access for specific IPs
- **Authenticated**: Full access with user accounts

## **8. Performance Optimizations**

### **Database**
- **Connection Pooling**: Configurable pool sizes for different environments
- **Indexing**: Strategic database indexes for search performance
- **Query Optimization**: Efficient filtering and pagination

### **Caching & Storage**
- **File Uploads**: Local storage with size limits
- **Generated Content**: Cloudinary for AI-generated images
- **Session Management**: Efficient session tracking

## **9. Monitoring & Analytics**

### **Usage Tracking**
- **LLM Usage Logs**: Token consumption and cost estimation
- **Error Logging**: Comprehensive error tracking
- **Free Tier Analytics**: IP-based usage monitoring
- **Performance Metrics**: Response times and success rates

This architecture provides a **scalable, secure, and feature-rich** AI knowledge management system that can handle multiple users, various AI models, and extensive document processing while maintaining performance and security standards suitable for production deployment on Railway.
