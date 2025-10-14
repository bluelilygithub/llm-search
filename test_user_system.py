"""
Test Script for Multi-User System
Comprehensive testing of user registration, authentication, and management
"""

import requests
import json
from datetime import datetime

class UserSystemTester:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
    
    def log_test(self, test_name, success, details=""):
        """Log test results"""
        result = {
            'test': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
    
    def test_health_check(self):
        """Test basic connectivity"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            success = response.status_code == 200
            self.log_test("Health Check", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Health Check", False, f"Error: {str(e)}")
            return False
    
    def test_migration_page(self):
        """Test migration page accessibility"""
        try:
            response = self.session.get(f"{self.base_url}/migrate-user-system")
            success = response.status_code == 200
            self.log_test("Migration Page Access", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Migration Page Access", False, f"Error: {str(e)}")
            return False
    
    def test_run_migration(self):
        """Test running the migration"""
        try:
            response = self.session.post(f"{self.base_url}/migrate-user-system")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                success = data.get('success', False)
                details = f"Migration result: {data.get('message', 'Unknown')}"
            else:
                details = f"HTTP {response.status_code}: {response.text[:100]}"
            
            self.log_test("Run Migration", success, details)
            return success
        except Exception as e:
            self.log_test("Run Migration", False, f"Error: {str(e)}")
            return False
    
    def test_user_registration(self, username="testuser", email="test@example.com", password="testpass123"):
        """Test user registration"""
        try:
            data = {
                "username": username,
                "email": email,
                "password": password,
                "first_name": "Test",
                "last_name": "User"
            }
            
            response = self.session.post(
                f"{self.base_url}/api/users/register",
                json=data,
                headers={'Content-Type': 'application/json'}
            )
            
            success = response.status_code == 201
            
            if success:
                result_data = response.json()
                details = f"User created: {result_data.get('user', {}).get('username', 'Unknown')}"
            else:
                details = f"HTTP {response.status_code}: {response.text[:100]}"
            
            self.log_test("User Registration", success, details)
            return success, response.json() if success else None
            
        except Exception as e:
            self.log_test("User Registration", False, f"Error: {str(e)}")
            return False, None
    
    def test_user_login(self, username="admin", password="admin123"):
        """Test user login"""
        try:
            data = {
                "username_or_email": username,
                "password": password
            }
            
            response = self.session.post(
                f"{self.base_url}/api/users/login",
                json=data,
                headers={'Content-Type': 'application/json'}
            )
            
            success = response.status_code == 200
            
            if success:
                result_data = response.json()
                user_info = result_data.get('user', {})
                details = f"Logged in as: {user_info.get('username')} (Role: {user_info.get('role')})"
                # Store session token for future requests
                self.session_token = result_data.get('session_token')
            else:
                details = f"HTTP {response.status_code}: {response.text[:100]}"
            
            self.log_test("User Login", success, details)
            return success, response.json() if success else None
            
        except Exception as e:
            self.log_test("User Login", False, f"Error: {str(e)}")
            return False, None
    
    def test_get_current_user(self):
        """Test getting current user profile"""
        try:
            response = self.session.get(f"{self.base_url}/api/users/me")
            success = response.status_code == 200
            
            if success:
                user_data = response.json().get('user', {})
                details = f"Current user: {user_data.get('username')} ({user_data.get('email')})"
            else:
                details = f"HTTP {response.status_code}: {response.text[:100]}"
            
            self.log_test("Get Current User", success, details)
            return success
            
        except Exception as e:
            self.log_test("Get Current User", False, f"Error: {str(e)}")
            return False
    
    def test_list_users(self):
        """Test listing users (admin only)"""
        try:
            response = self.session.get(f"{self.base_url}/api/users/")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                user_count = len(data.get('users', []))
                details = f"Found {user_count} users"
            else:
                details = f"HTTP {response.status_code}: {response.text[:100]}"
            
            self.log_test("List Users (Admin)", success, details)
            return success
            
        except Exception as e:
            self.log_test("List Users (Admin)", False, f"Error: {str(e)}")
            return False
    
    def test_user_logout(self):
        """Test user logout"""
        try:
            response = self.session.post(f"{self.base_url}/api/users/logout")
            success = response.status_code == 200
            
            details = "Logout successful" if success else f"HTTP {response.status_code}"
            self.log_test("User Logout", success, details)
            return success
            
        except Exception as e:
            self.log_test("User Logout", False, f"Error: {str(e)}")
            return False
    
    def run_full_test_suite(self):
        """Run complete test suite"""
        print("🧪 Starting Multi-User System Tests")
        print("=" * 50)
        
        # Basic connectivity
        if not self.test_health_check():
            print("❌ Cannot connect to server. Make sure the app is running.")
            return False
        
        # Test migration system
        print("\n📋 Testing Migration System:")
        self.test_migration_page()
        
        # Try to run migration (might fail if already run)
        migration_success = self.test_run_migration()
        
        # Test authentication flow
        print("\n🔐 Testing Authentication:")
        
        # Try login with default admin credentials
        login_success, login_data = self.test_user_login("admin", "admin123")
        
        if login_success:
            # Test authenticated endpoints
            self.test_get_current_user()
            self.test_list_users()
            
            # Test user registration
            print("\n👥 Testing User Management:")
            reg_success, reg_data = self.test_user_registration()
            
            # Test logout
            self.test_user_logout()
        
        # Print summary
        print("\n📊 Test Summary:")
        print("=" * 50)
        
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        
        print(f"Tests Passed: {passed}/{total}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if passed < total:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['details']}")
        
        return passed == total

def main():
    """Run the test suite"""
    print("🚀 Multi-User System Testing Tool")
    print("=" * 50)
    
    # Check if server is running locally
    tester = UserSystemTester("http://localhost:5000")
    
    print("Testing locally at http://localhost:5000")
    print("Make sure your Flask app is running with: python app.py")
    print()
    
    success = tester.run_full_test_suite()
    
    if success:
        print("\n🎉 All tests passed! Multi-user system is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Check the details above.")
    
    return success

if __name__ == '__main__':
    main()
