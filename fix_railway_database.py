"""
Run this script on Railway to fix the user_id column type
Railway CLI: railway run python fix_railway_database.py
"""
import os
from sqlalchemy import create_engine, text

# Get database URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found")
    exit(1)

print(f"Connecting to database...")
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        print("✓ Connected to database")
        
        # Check current column type
        print("\n1. Checking current column type...")
        result = conn.execute(text("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns 
            WHERE table_name = 'conversations' AND column_name = 'user_id'
        """))
        row = result.fetchone()
        print(f"   Current type: {row[1]} ({row[2]})")
        
        if row[1] == 'uuid':
            print("   ✓ Column is already UUID, no changes needed!")
            exit(0)
        
        # Drop the VARCHAR column
        print("\n2. Dropping old VARCHAR column...")
        conn.execute(text("ALTER TABLE conversations DROP COLUMN IF EXISTS user_id CASCADE"))
        conn.commit()
        print("   ✓ Dropped")
        
        # Add UUID column
        print("\n3. Adding new UUID column...")
        conn.execute(text("ALTER TABLE conversations ADD COLUMN user_id UUID"))
        conn.commit()
        print("   ✓ Added")
        
        # Add foreign key
        print("\n4. Adding foreign key constraint...")
        conn.execute(text("""
            ALTER TABLE conversations
            ADD CONSTRAINT fk_conversations_user 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        """))
        conn.commit()
        print("   ✓ Added")
        
        # Create index
        print("\n5. Creating index...")
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)"))
        conn.commit()
        print("   ✓ Created")
        
        # Link existing conversations to admin
        print("\n6. Linking conversations to admin user...")
        result = conn.execute(text("""
            UPDATE conversations 
            SET user_id = (SELECT id FROM users WHERE username = 'admin' LIMIT 1)
            WHERE user_id IS NULL
        """))
        conn.commit()
        print(f"   ✓ Updated {result.rowcount} conversations")
        
        # Verify
        print("\n7. Verifying...")
        result = conn.execute(text("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns 
            WHERE table_name = 'conversations' AND column_name = 'user_id'
        """))
        row = result.fetchone()
        print(f"   Final type: {row[1]} ({row[2]})")
        
        if row[1] == 'uuid':
            print("\n✅ SUCCESS! user_id is now UUID")
        else:
            print(f"\n❌ FAILED! user_id is still {row[1]}")
            
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    exit(1)

