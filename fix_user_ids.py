#!/usr/bin/env python3
"""
Migration script to fix IP-based user_ids for authenticated users.
This script updates conversations created with IP-based user_ids to use 'admin'.
"""

import os
import sys
from datetime import datetime

# Add the app directory to path
sys.path.append(os.path.dirname(__file__))

def fix_user_ids():
    """Fix IP-based user_ids in conversations table"""
    try:
        # Set up the Flask app context
        from app import app, db
        from models import Conversation
        
        with app.app_context():
            print("🔍 Checking for conversations with IP-based user_ids...")
            
            # Find conversations with old IP-based user_ids (pattern: auth_[16-char hex])
            old_conversations = db.session.query(Conversation).filter(
                Conversation.user_id.like('auth_%')
            ).all()
            
            if not old_conversations:
                print("✅ No conversations found with old IP-based user_ids.")
                return
            
            print(f"📝 Found {len(old_conversations)} conversations with old user_ids:")
            
            # Group by user_id to show what we're fixing
            user_id_counts = {}
            for conv in old_conversations:
                user_id_counts[conv.user_id] = user_id_counts.get(conv.user_id, 0) + 1
            
            for user_id, count in user_id_counts.items():
                print(f"   - {user_id}: {count} conversations")
            
            # Ask for confirmation
            response = input(f"\n🔄 Update all {len(old_conversations)} conversations to use user_id='admin'? (y/N): ")
            if response.lower() != 'y':
                print("❌ Migration cancelled.")
                return
            
            # Update all conversations
            updated_count = db.session.query(Conversation).filter(
                Conversation.user_id.like('auth_%')
            ).update(
                {'user_id': 'admin', 'updated_at': datetime.utcnow()}, 
                synchronize_session=False
            )
            
            db.session.commit()
            
            print(f"✅ Successfully updated {updated_count} conversations to use user_id='admin'")
            print("🎉 Your conversations should now be visible!")
            
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_user_ids()