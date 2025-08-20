-- Migration script to add user identification columns to conversations table
-- Run this SQL on your PostgreSQL database

-- Add the new columns to the conversations table (ignore if they exist)
DO $$ 
BEGIN
    BEGIN
        ALTER TABLE conversations ADD COLUMN user_id VARCHAR(100);
    EXCEPTION
        WHEN duplicate_column THEN NULL;
    END;
    
    BEGIN
        ALTER TABLE conversations ADD COLUMN session_id VARCHAR(100);
    EXCEPTION
        WHEN duplicate_column THEN NULL;
    END;
    
    BEGIN
        ALTER TABLE conversations ADD COLUMN ip_address VARCHAR(45);
    EXCEPTION
        WHEN duplicate_column THEN NULL;
    END;
END $$;

-- Create indexes for better query performance (ignore if they exist)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_conversations_user_id') THEN
        CREATE INDEX idx_conversations_user_id ON conversations(user_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_conversations_session_id') THEN
        CREATE INDEX idx_conversations_session_id ON conversations(session_id);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_conversations_ip_address') THEN
        CREATE INDEX idx_conversations_ip_address ON conversations(ip_address);
    END IF;
END $$;

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