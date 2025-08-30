#!/usr/bin/env python3
"""
Test script to verify session ID generation and user identity functionality
"""

import os
import sys
import uuid

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock Flask request and session for testing
class MockRequest:
    def __init__(self):
        self.cookies = {}
        self.remote_addr = '127.0.0.1'

class MockSession:
    def __init__(self):
        self.data = {}
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def __setitem__(self, key, value):
        self.data[key] = value

# Mock Flask app context
class MockAppContext:
    def __init__(self):
        self.request = MockRequest()
        self.session = MockSession()

# Set up mock environment
import flask
flask.request = MockRequest()
flask.session = MockSession()

# Test the get_user_identity function
def test_get_user_identity():
    print("Testing get_user_identity function...")
    
    try:
        from security_utils import get_user_identity
        
        # Test 1: No existing session cookie
        print("\nTest 1: No existing session cookie")
        identity = get_user_identity()
        print(f"Result: {identity}")
        assert identity['type'] == 'free'
        assert identity['session_id'] is not None
        print("✓ PASSED: Generated new session ID")
        
        # Test 2: With existing session cookie
        print("\nTest 2: With existing session cookie")
        test_session_id = str(uuid.uuid4())
        flask.request.cookies['session_id'] = test_session_id
        identity = get_user_identity()
        print(f"Result: {identity}")
        assert identity['session_id'] == test_session_id
        print("✓ PASSED: Used existing session cookie")
        
        # Test 3: Clear cookies and test again
        print("\nTest 3: Clear cookies and test again")
        flask.request.cookies = {}
        identity = get_user_identity()
        print(f"Result: {identity}")
        assert identity['type'] == 'free'
        assert identity['session_id'] is not None
        print("✓ PASSED: Generated new session ID after clearing cookies")
        
        print("\n🎉 All tests passed! get_user_identity function is working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_get_user_identity()
    sys.exit(0 if success else 1)
