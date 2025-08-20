-- Migration script to add user identification columns to conversations table
-- Run this SQL on your PostgreSQL database

-- Add the new columns to the conversations table
ALTER TABLE conversations 
ADD COLUMN user_id VARCHAR(100),
ADD COLUMN session_id VARCHAR(100),
ADD COLUMN ip_address VARCHAR(45);

-- Create indexes for better query performance
CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_session_id ON conversations(session_id);
CREATE INDEX idx_conversations_ip_address ON conversations(ip_address);

-- Optional: Update existing conversations with a placeholder
-- You may want to review this based on your specific needs
-- This will help identify "legacy" conversations vs new ones
UPDATE conversations 
SET session_id = 'legacy-' || id::text
WHERE user_id IS NULL AND session_id IS NULL;

-- Verify the migration
SELECT 
    COUNT(*) as total_conversations,
    COUNT(user_id) as authenticated_conversations,
    COUNT(session_id) as session_conversations,
    COUNT(ip_address) as ip_tracked_conversations
FROM conversations;