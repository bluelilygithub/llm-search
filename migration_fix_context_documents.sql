-- Migration script to fix context_documents column issue
-- Run this SQL on your PostgreSQL database

-- Update existing conversations where context_documents is NULL to have an empty array
UPDATE conversations 
SET context_documents = '[]'::jsonb
WHERE context_documents IS NULL;

-- Verify the migration
SELECT 
    COUNT(*) as total_conversations,
    COUNT(CASE WHEN context_documents IS NULL THEN 1 END) as null_context_docs,
    COUNT(CASE WHEN context_documents IS NOT NULL THEN 1 END) as has_context_docs
FROM conversations;
