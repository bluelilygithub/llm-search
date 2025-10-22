#!/usr/bin/env python3
"""
Database restoration verification script
Run this after executing RESTORE_DATABASE.sql to verify everything is working
"""

import os
import sys
from flask import Flask
from database import db
from models import Conversation, Message, ContextItem

def test_database_restoration():
    """Test that the database is working after restoration"""
    
    print("🧪 Testing Database Restoration")
    print("=" * 50)
    
    # Initialize Flask app
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'test-secret-key')
    
    db.init_app(app)
    
    with app.app_context():
        try:
            # Test 1: Check if we can query conversations
            print("\n🔍 Test 1: Query conversations")
            conv_count = Conversation.query.count()
            print(f"   ✅ Found {conv_count} conversations")
            
            # Test 2: Check if we can query messages
            print("\n🔍 Test 2: Query messages")
            msg_count = Message.query.count()
            print(f"   ✅ Found {msg_count} messages")
            
            # Test 3: Check if we can query context_items
            print("\n🔍 Test 3: Query context_items")
            ctx_count = ContextItem.query.count()
            print(f"   ✅ Found {ctx_count} context items")
            
            # Test 4: Check if we can create a test conversation
            print("\n🔍 Test 4: Create test conversation")
            test_conv = Conversation(
                title="Test Conversation",
                llm_model="gpt-4",
                user_id="test-user"
            )
            db.session.add(test_conv)
            db.session.commit()
            print(f"   ✅ Created test conversation: {test_conv.id}")
            
            # Test 5: Check if we can update context_documents
            print("\n🔍 Test 5: Test context_documents update")
            test_conv.context_documents = [{"filename": "test.txt", "content": "test content"}]
            db.session.commit()
            print(f"   ✅ Updated context_documents")
            
            # Clean up test data
            db.session.delete(test_conv)
            db.session.commit()
            print("   🧹 Cleaned up test data")
            
            print("\n🎉 All tests passed! Database is working correctly.")
            return True
            
        except Exception as e:
            print(f"❌ Test failed with error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    success = test_database_restoration()
    sys.exit(0 if success else 1)
