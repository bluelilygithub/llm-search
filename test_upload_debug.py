#!/usr/bin/env python3
"""
Quick test script to debug the upload issue
"""

import os
import sys
from flask import Flask
from database import db
from context_service import ContextService
from security_utils import get_user_identity

def test_user_id():
    """Test the user_id resolution"""
    
    print("🧪 Testing User ID Resolution")
    print("=" * 50)
    
    # Initialize Flask app
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'test-secret-key')
    
    db.init_app(app)
    
    with app.app_context():
        try:
            # Test 1: Check get_user_identity
            print("\n🔍 Test 1: get_user_identity()")
            identity = get_user_identity()
            print(f"   Identity: {identity}")
            print(f"   User ID: {identity.get('user_id')}")
            print(f"   Type: {identity.get('type')}")
            
            # Test 2: Check ContextService.get_user_id
            print("\n🔍 Test 2: ContextService.get_user_id()")
            user_id = ContextService.get_user_id()
            print(f"   User ID: {user_id}")
            print(f"   Type: {type(user_id)}")
            
            # Test 3: Try to create a context item
            print("\n🔍 Test 3: Create test context item")
            try:
                context_item = ContextService.create_context_item(
                    name="test-upload.txt",
                    content_type="document",
                    content_text="This is a test document",
                    description="Test upload"
                )
                print(f"   ✅ Successfully created context item: {context_item.id}")
                print(f"   User ID in item: {context_item.user_id}")
                
                # Clean up
                db.session.delete(context_item)
                db.session.commit()
                print("   🧹 Cleaned up test item")
                
            except Exception as e:
                print(f"   ❌ Failed to create context item: {str(e)}")
                import traceback
                traceback.print_exc()
            
            print("\n🎉 Test completed!")
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
    
    success = test_user_id()
    sys.exit(0 if success else 1)
