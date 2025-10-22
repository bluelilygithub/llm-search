# Conversational RAG Implementation Guide

## Overview

This document describes the implementation of **Conversational RAG** - extending the existing RAG (Retrieval-Augmented Generation) system to include semantic search across conversations, messages, and past AI responses in addition to uploaded documents.

## What Was Implemented

### 1. Database Schema Changes

**New Columns Added:**

#### Conversations Table
- `embedding` (vector(1536)) - Vector embedding of conversation summary
- `embedding_processed` (boolean) - Flag indicating if embedding was generated
- `embedding_processed_at` (timestamp) - When the embedding was created

#### Messages Table
- `embedding` (vector(1536)) - Vector embedding of message content
- `embedding_processed` (boolean) - Flag indicating if embedding was generated

**Indexes Created:**
- IVFFlat index on `conversations.embedding` for fast vector similarity search
- IVFFlat index on `messages.embedding` for fast vector similarity search

### 2. New Files Created

#### `rag_service_enhanced.py`
Enhanced RAG service with the following capabilities:

**Message Processing:**
- `process_message(message_id)` - Generate embedding for a single message
- `process_conversation_messages(conversation_id)` - Process all messages in a conversation

**Conversation Processing:**
- `process_conversation(conversation_id)` - Generate summary embedding for conversation (title + tags + first exchanges)

**Semantic Search:**
- `search_messages(query, user_id, threshold, max_results)` - Search messages using vector similarity
- `search_conversations(query, user_id, threshold, max_results)` - Search conversations
- `search_all(query, user_id, threshold, max_results)` - Search across all sources (documents, conversations, messages)

**Context Retrieval:**
- `get_context_for_query(query, user_id, max_length)` - Get relevant context from all sources for AI prompt enhancement

**Batch Processing:**
- `process_all_user_data(user_id)` - Process all conversations and messages for a user

#### `MIGRATION_ADD_VECTOR_EMBEDDINGS.sql`
SQL migration script to:
- Enable pgvector extension
- Add embedding columns to tables
- Create vector similarity indexes
- Add performance indexes

### 3. API Endpoints Added

#### Processing Endpoints
- `POST /api/rag/process-conversation` - Process single conversation
- `POST /api/rag/process-all-conversations` - Process all conversations for current user

#### Search Endpoints
- `POST /api/rag/search-conversations` - Search conversations by semantic similarity
- `POST /api/rag/search-messages` - Search messages by semantic similarity
- `POST /api/rag/search-all` - Search across all sources

### 4. Enhanced Chat Endpoint

The main `/chat` endpoint now:
- Uses `EnhancedRAGService` instead of `SimpleRAGService`
- Searches across documents, conversations, and messages
- Provides richer context (up to 3000 characters instead of 2000)
- Shows source types in citations (document vs conversation)
- Informs AI that context includes "previous conversations and past AI responses"

## How It Works

### Document Processing Flow

1. **User uploads document** → Stored in `context_items` table
2. **Document is processed** → Chunked and embeddings generated (existing system)
3. **User has conversation** → Stored in `conversations` and `messages` tables
4. **Conversation is processed** → Embeddings generated for conversation summary and each message
5. **User asks new question** → System searches ALL sources:
   - Uploaded documents (chunks)
   - Previous conversations (summaries)
   - Past messages (individual Q&A pairs)
6. **Most relevant content retrieved** → Added to AI prompt
7. **AI responds** → With context from documents + conversation history

### Embedding Generation

**For Documents:**
- Chunked into 1000-character pieces with 200-character overlap
- Each chunk gets an embedding (stored in `context_items.extra_data`)

**For Conversations:**
- Summary created: Title + Tags + First 6 messages (truncated)
- Single embedding represents the entire conversation
- Helps find "conversations about X"

**For Messages:**
- Each message (user question or AI answer) gets its own embedding
- Enables finding specific Q&A pairs
- More granular than conversation-level search

### Search Strategy

When user asks a question:

1. **Generate query embedding** - Convert question to vector
2. **Search all sources** using cosine similarity:
   - Documents: Search document chunks
   - Conversations: Search conversation summaries
   - Messages: Search individual messages
3. **Rank by relevance** - Sort all results by similarity score
4. **Build context** - Take top results up to 3000 characters
5. **Enhance prompt** - Add context to system message
6. **Generate response** - AI uses full context to answer

## Deployment Steps

### Step 1: Install pgvector

```bash
# Install pgvector Python package
pip install pgvector==0.2.4
```

### Step 2: Run Database Migration

```bash
# Connect to your PostgreSQL database
psql $DATABASE_URL -f MIGRATION_ADD_VECTOR_EMBEDDINGS.sql
```

This will:
- Enable the vector extension
- Add embedding columns
- Create indexes
- Verify changes

### Step 3: Process Existing Data

After deployment, you need to process existing conversations:

**Option A: Process All User Data (Recommended)**
```bash
# Via API endpoint
curl -X POST https://your-app.com/api/rag/process-all-conversations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Option B: Process Individual Conversations**
```bash
curl -X POST https://your-app.com/api/rag/process-conversation \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"conversation_id": "CONVERSATION_UUID"}'
```

### Step 4: Verify Implementation

**Test Search:**
```bash
# Search all sources
curl -X POST https://your-app.com/api/rag/search-all \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "how do I reset a password",
    "max_results": 10,
    "similarity_threshold": 0.65
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "query": "how do I reset a password",
  "results": {
    "messages": [...],
    "conversations": [...],
    "documents": [...],
    "all_results": [...]
  },
  "total_results": 10,
  "messages_count": 4,
  "conversations_count": 2,
  "documents_count": 4
}
```

## Performance Considerations

### Embedding Generation

- **Cost:** Each message processed costs ~$0.00001 (OpenAI text-embedding-3-small)
- **Speed:** ~1-2 seconds per conversation (including all messages)
- **Batch Processing:** Process in batches to avoid timeouts

### Vector Search

- **IVFFlat Index:** Provides approximate nearest neighbor search
- **Speed:** Sub-second search across thousands of vectors
- **Memory:** ~6KB per embedding (1536 floats × 4 bytes)

### Recommendations

1. **Process conversations incrementally** - Don't process all at once
2. **Auto-process new conversations** - Add trigger to process after conversation ends
3. **Monitor costs** - Track OpenAI embedding API usage
4. **Adjust thresholds** - Tune similarity thresholds based on results quality

## Usage Examples

### Example 1: Find Past Solutions

**User Question:** "How did we solve the database timeout issue?"

**RAG Process:**
1. Searches messages for "database timeout"
2. Finds answer from 2 months ago
3. Includes that answer in context
4. AI responds: "Based on our previous conversation from March..."

### Example 2: Reference Documents + History

**User Question:** "What are the requirements for user passwords?"

**RAG Process:**
1. Searches documents for password requirements
2. Searches messages for password discussions
3. Combines both in context
4. AI responds with documentation + past clarifications

### Example 3: Project Memory

**User Question:** "What features did we decide on for the dashboard?"

**RAG Process:**
1. Searches conversations in Dashboard project
2. Finds relevant planning discussions
3. AI responds with comprehensive feature list from past conversations

## Troubleshooting

### Issue: No results returned

**Causes:**
- Conversations haven't been processed yet
- Similarity threshold too high
- No relevant content exists

**Solutions:**
- Run `process-all-conversations` endpoint
- Lower similarity threshold to 0.5
- Check that embeddings were generated

### Issue: Slow searches

**Causes:**
- Missing indexes
- Too many results requested
- Database not optimized

**Solutions:**
- Verify indexes were created: `\d+ conversations` in psql
- Reduce max_results parameter
- Run `VACUUM ANALYZE` on database

### Issue: Out of memory

**Causes:**
- Processing too many conversations at once
- Large message content

**Solutions:**
- Process conversations in smaller batches
- Truncate message content before embedding (already implemented)
- Increase Railway memory limit

## Future Enhancements

### Possible Improvements

1. **Auto-processing** - Automatically process conversations after they end
2. **Conversation clustering** - Group related conversations
3. **Temporal search** - Weight recent conversations higher
4. **Project-aware search** - Filter by project context
5. **User collaboration** - Search shared conversations (with permissions)
6. **Conversation summaries** - Auto-generate conversation titles from embeddings
7. **Similarity visualization** - Show relationship graphs between conversations

### Advanced Features

1. **Hybrid search** - Combine vector search with full-text search
2. **Re-ranking** - Use cross-encoder for better relevance
3. **Conversation threads** - Track conversation branching
4. **Knowledge graphs** - Extract entities and relationships
5. **Multi-lingual** - Support embeddings in multiple languages

## Monitoring

### Key Metrics to Track

1. **Processing Status:**
   ```sql
   SELECT 
     COUNT(*) as total_conversations,
     SUM(CASE WHEN embedding_processed THEN 1 ELSE 0 END) as processed,
     SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as has_embedding
   FROM conversations;
   ```

2. **Search Performance:**
   ```sql
   EXPLAIN ANALYZE
   SELECT id, title, 1 - (embedding <=> '[...]') as similarity
   FROM conversations
   WHERE embedding IS NOT NULL
   ORDER BY embedding <=> '[...]'
   LIMIT 10;
   ```

3. **Storage Usage:**
   ```sql
   SELECT 
     pg_size_pretty(pg_total_relation_size('conversations')) as conversations_size,
     pg_size_pretty(pg_total_relation_size('messages')) as messages_size;
   ```

## Cost Estimation

### Embedding Generation (One-time)

- **10,000 messages** × $0.00001 = **$0.10**
- **1,000 conversations** × $0.00001 = **$0.01**
- **Total initial processing: ~$0.11**

### Ongoing Costs

- **Per new conversation:** $0.00001 (conversation) + $0.0001 (10 messages) = **$0.00011**
- **Per search query:** $0.00001 (query embedding)

### Monthly Estimate (1000 active users)

- 10 conversations/user/month = 10,000 conversations
- 10,000 × $0.00011 = **$1.10/month for embeddings**
- 100,000 queries = 100,000 × $0.00001 = **$1.00/month for searches**
- **Total: ~$2.10/month** (very affordable!)

## Security & Privacy

### User Isolation

- **All searches filtered by user_id** - Users only see their own data
- **Embeddings are user-specific** - No cross-user information leakage
- **Project-level filtering** - Can restrict to specific projects

### Data Protection

- **Embeddings are not human-readable** - Cannot reverse engineer original text
- **No data leaves your database** - All vector operations happen in PostgreSQL
- **Standard access controls apply** - Existing auth system protects all endpoints

## Conclusion

Conversational RAG transforms your knowledge base from a document repository into a **true institutional memory** that learns from every interaction. Users can now ask questions and get answers informed by:

✅ **Documents they've uploaded**  
✅ **Conversations they've had**  
✅ **Solutions that worked in the past**  
✅ **Context across their entire history**

This creates a **cumulative knowledge effect** where the system gets smarter over time as users interact with it.

