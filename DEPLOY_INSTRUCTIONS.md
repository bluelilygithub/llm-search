# Deployment Instructions for Conversational RAG

## Current Status
✅ Code has been rolled back to use Simple RAG (documents only)  
✅ App should be working now  
⏳ Conversational RAG ready to enable after migration  

## What Happened
The app tried to use new database columns (`conversations.embedding`, `messages.embedding`) that don't exist yet, causing the error you saw.

## Quick Fix Applied
I've temporarily commented out the new columns in `models.py` and reverted the chat endpoint to use `SimpleRAGService` (documents only). This means:
- ✅ Your app works NOW
- ✅ Conversations and chats appear
- ✅ Document RAG still works
- ⏳ Conversational RAG disabled until migration runs

## Steps to Enable Full Conversational RAG

### Step 1: Deploy Current Changes (App Works Now)
```bash
git add .
git commit -m "Rollback to simple RAG until migration runs"
git push
```

Your app should be working now on Railway!

### Step 2: Run Database Migration

**Via Railway Dashboard:**
1. Go to https://railway.app/dashboard
2. Click on your **PostgreSQL** service (not your app)
3. Click **"Query"** or **"Data"** tab
4. Copy the entire contents of `RAILWAY_MIGRATION.sql`
5. Paste into the query box
6. Click **"Run Query"** or **"Execute"**
7. You should see: "Migration completed successfully!"

**The migration adds:**
- pgvector extension
- `embedding` columns to conversations and messages
- Indexes for fast vector search

### Step 3: Enable Conversational RAG

After the migration succeeds, uncomment the code:

**In `models.py`:**
```python
# Change lines 51-54 FROM:
# TODO: Uncomment after running RAILWAY_MIGRATION.sql
# embedding = db.Column(Vector(1536), nullable=True)
# embedding_processed = db.Column(db.Boolean, default=False)
# embedding_processed_at = db.Column(db.DateTime, nullable=True)

# TO:
embedding = db.Column(Vector(1536), nullable=True)
embedding_processed = db.Column(db.Boolean, default=False)
embedding_processed_at = db.Column(db.DateTime, nullable=True)

# AND lines 68-70 FROM:
# TODO: Uncomment after running RAILWAY_MIGRATION.sql
# embedding = db.Column(Vector(1536), nullable=True)
# embedding_processed = db.Column(db.Boolean, default=False)

# TO:
embedding = db.Column(Vector(1536), nullable=True)
embedding_processed = db.Column(db.Boolean, default=False)
```

**In `app.py` line 1777:**
```python
# Change FROM:
from rag_service_simple import SimpleRAGService

# TO:
from rag_service_enhanced import EnhancedRAGService
```

**And update the service initialization (lines 1783-1793):**
```python
# Change FROM:
rag_service = SimpleRAGService(
    openai_api_key=os.getenv('OPENAI_API_KEY')
)

rag_context = rag_service.get_context_for_query(
    query=user_message,
    max_context_length=2000,
    user_id=user_id
)

# TO:
rag_service = EnhancedRAGService(
    openai_api_key=os.getenv('OPENAI_API_KEY'),
    db_session=db.session
)

rag_context = rag_service.get_context_for_query(
    query=user_message,
    max_context_length=3000,
    user_id=user_id
)
```

**And update the source formatting (lines 1797-1805):**
```python
# Replace the entire search_results and rag_sources section with:
search_results = rag_service.search_all(
    query=user_message,
    user_id=user_id,
    similarity_threshold=0.65,
    max_results=5
)

# Format sources for display
for result in search_results.get('all_results', [])[:5]:
    source_type = result.get('source_type')
    if source_type == 'document':
        rag_sources.append({
            'type': 'document',
            'name': result.get('document_name'),
            'score': result.get('similarity_score')
        })
    elif source_type == 'message':
        rag_sources.append({
            'type': 'conversation',
            'name': result.get('conversation_title'),
            'score': result.get('similarity_score')
        })
    elif source_type == 'conversation':
        rag_sources.append({
            'type': 'conversation',
            'name': result.get('title'),
            'score': result.get('similarity_score')
        })
```

Then deploy:
```bash
git add .
git commit -m "Enable full conversational RAG"
git push
```

### Step 4: Process Existing Conversations

After enabling conversational RAG, you need to process your existing conversations to generate embeddings:

**Via API:**
```bash
# Replace with your Railway URL
curl -X POST https://your-app.railway.app/api/rag/process-all-conversations \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

**Or add an admin button** to trigger processing from the UI.

## Timeline

**Now (Immediate):**
- ✅ App is working
- ✅ Document RAG functional
- ⏸️ Conversational RAG disabled

**After Migration (5 minutes):**
- ✅ Database ready for vector embeddings
- ⏸️ Need to uncomment code

**After Code Update (5 minutes):**
- ✅ Conversational RAG enabled
- ⏳ Conversations need processing

**After Processing (1-5 minutes depending on data):**
- ✅ Full conversational RAG operational
- ✅ AI can reference past conversations
- ✅ Search across all knowledge sources

## Troubleshooting

### If Railway query interface is hard to find:
1. Go to your project
2. Click the PostgreSQL service card
3. Look for tabs: "Variables", "Metrics", "Settings", **"Query"** or **"Data"**
4. The query interface should be there

### If you can't find the query interface:
Use Railway CLI:
```bash
railway login
railway link
railway connect postgres
```
Then paste the SQL from `RAILWAY_MIGRATION.sql`

### If migration fails:
Check if pgvector extension is available:
```sql
SELECT * FROM pg_available_extensions WHERE name = 'vector';
```

If not available, contact Railway support to enable it.

## Questions?

- App not working? Check Railway logs for errors
- Migration issues? Share the error message
- Need help enabling conversational RAG? Let me know!

