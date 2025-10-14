#!/usr/bin/env python3
"""
Database Index Migration Script
Adds essential performance indexes to the PostgreSQL database
Railway-compatible with proper error handling and rollback
"""

import os
import sys
import psycopg2
from psycopg2 import sql
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment variables"""
    # Railway provides DATABASE_URL
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url
    
    # Fallback to individual components
    host = os.getenv('PGHOST', 'localhost')
    port = os.getenv('PGPORT', '5432')
    database = os.getenv('PGDATABASE', 'postgres')
    user = os.getenv('PGUSER', 'postgres')
    password = os.getenv('PGPASSWORD', '')
    
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"

def check_table_exists(cursor, table_name):
    """Check if a table exists in the database"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        );
    """, (table_name,))
    return cursor.fetchone()[0]

def check_index_exists(cursor, index_name):
    """Check if an index already exists"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM pg_class c 
            JOIN pg_namespace n ON n.oid = c.relnamespace 
            WHERE c.relkind = 'i' 
            AND n.nspname = 'public' 
            AND c.relname = %s
        );
    """, (index_name,))
    return cursor.fetchone()[0]

def create_index_safely(cursor, index_sql, index_name):
    """Create an index with error handling"""
    try:
        if check_index_exists(cursor, index_name):
            logger.info(f"Index {index_name} already exists, skipping")
            return True
            
        logger.info(f"Creating index: {index_name}")
        cursor.execute(index_sql)
        logger.info(f"✓ Created index: {index_name}")
        return True
        
    except psycopg2.Error as e:
        logger.error(f"✗ Failed to create index {index_name}: {e}")
        return False

def main():
    """Main migration function"""
    logger.info("Starting database index migration...")
    
    # Get database connection
    try:
        db_url = get_database_url()
        if not db_url:
            logger.error("No database URL found in environment variables")
            return False
            
        conn = psycopg2.connect(db_url)
        conn.autocommit = False  # Use transactions
        cursor = conn.cursor()
        
        logger.info("Connected to database successfully")
        
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return False
    
    # Check required tables exist
    required_tables = [
        'conversations', 'messages', 'projects', 'context_items'
    ]
    
    missing_tables = []
    for table in required_tables:
        if not check_table_exists(cursor, table):
            missing_tables.append(table)
    
    if missing_tables:
        logger.error(f"Missing required tables: {missing_tables}")
        return False
    
    logger.info("All required tables found")
    
    # Define indexes to create
    indexes = [
        # Conversations indexes
        {
            'name': 'idx_conversations_user_created',
            'sql': """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_user_created 
                ON conversations(user_id, created_at DESC)
            """
        },
        {
            'name': 'idx_conversations_session_created',
            'sql': """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_session_created 
                ON conversations(session_id, created_at DESC)
            """
        },
        {
            'name': 'idx_conversations_project_created',
            'sql': """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_project_created 
                ON conversations(project_id, created_at DESC)
            """
        },
        {
            'name': 'idx_conversations_user_project',
            'sql': """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_user_project 
                ON conversations(user_id, project_id, updated_at DESC)
            """
        },
        
        # Messages indexes
        {
            'name': 'idx_messages_conversation_timestamp',
            'sql': """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_conversation_timestamp 
                ON messages(conversation_id, timestamp ASC)
            """
        },
        {
            'name': 'idx_messages_conversation_role',
            'sql': """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_conversation_role 
                ON messages(conversation_id, role, timestamp ASC)
            """
        },
        
        # Context items indexes
        {
            'name': 'idx_context_items_user_active',
            'sql': """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_context_items_user_active 
                ON context_items(user_id, is_active, created_at DESC)
            """
        },
        {
            'name': 'idx_context_items_project_active',
            'sql': """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_context_items_project_active 
                ON context_items(project_id, is_active, created_at DESC)
            """
        }
    ]
    
    # Add conditional indexes for tables that might not exist
    optional_indexes = [
        {
            'table': 'context_sessions',
            'name': 'idx_context_sessions_conversation',
            'sql': """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_context_sessions_conversation 
                ON context_sessions(conversation_id, created_at DESC)
            """
        },
        {
            'table': 'llm_usage_logs',
            'name': 'idx_llm_usage_conversation_timestamp',
            'sql': """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_llm_usage_conversation_timestamp 
                ON llm_usage_logs(conversation_id, timestamp DESC)
            """
        },
        {
            'table': 'llm_usage_logs',
            'name': 'idx_llm_usage_model_timestamp',
            'sql': """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_llm_usage_model_timestamp 
                ON llm_usage_logs(model, timestamp DESC)
            """
        },
        {
            'table': 'free_access_logs',
            'name': 'idx_free_access_ip_timestamp',
            'sql': """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_free_access_ip_timestamp 
                ON free_access_logs(ip_address, timestamp DESC)
            """
        }
    ]
    
    success_count = 0
    total_count = 0
    
    try:
        # Create core indexes
        logger.info("Creating core indexes...")
        for index in indexes:
            total_count += 1
            if create_index_safely(cursor, index['sql'], index['name']):
                success_count += 1
        
        # Create optional indexes (only if tables exist)
        logger.info("Creating optional indexes...")
        for index in optional_indexes:
            if check_table_exists(cursor, index['table']):
                total_count += 1
                if create_index_safely(cursor, index['sql'], index['name']):
                    success_count += 1
            else:
                logger.info(f"Table {index['table']} not found, skipping {index['name']}")
        
        # Commit the transaction
        conn.commit()
        logger.info(f"Migration completed: {success_count}/{total_count} indexes created successfully")
        
        # Update table statistics
        logger.info("Updating table statistics...")
        tables_to_analyze = ['conversations', 'messages', 'projects', 'context_items']
        for table in tables_to_analyze:
            if check_table_exists(cursor, table):
                cursor.execute(f"ANALYZE {table}")
                logger.info(f"✓ Analyzed table: {table}")
        
        conn.commit()
        
        # Show created indexes
        logger.info("Verifying created indexes...")
        cursor.execute("""
            SELECT tablename, indexname 
            FROM pg_indexes 
            WHERE tablename IN ('conversations', 'messages', 'projects', 'context_items')
            AND indexname LIKE 'idx_%'
            ORDER BY tablename, indexname
        """)
        
        indexes_found = cursor.fetchall()
        logger.info(f"Found {len(indexes_found)} performance indexes:")
        for table, index in indexes_found:
            logger.info(f"  {table}: {index}")
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        return False
        
    finally:
        cursor.close()
        conn.close()
        logger.info("Database connection closed")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
