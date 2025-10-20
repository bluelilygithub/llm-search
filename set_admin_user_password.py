#!/usr/bin/env python3
"""
Set Admin User Password in Database
Run this AFTER running the database migration
"""

from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def set_admin_password():
    """Set the admin user password in the database"""
    
    # Get password from environment or prompt
    password = os.getenv('AUTH_PASSWORD')
    
    if not password:
        print("❌ No AUTH_PASSWORD found in .env file")
        print("Please set AUTH_PASSWORD in your .env file first")
        return
    
    # Check if password is already hashed
    if password.startswith(('$2b$', '$2a$', '$2y$', 'pbkdf2:', 'scrypt:')):
        print("✅ Password is already hashed")
        hashed_password = password
    else:
        print("⚠️  Password is plaintext, hashing it...")
        hashed_password = generate_password_hash(password)
    
    print("\n" + "="*60)
    print("ADMIN USER PASSWORD HASH")
    print("="*60)
    print("\nCopy this hash and run this SQL in DBeaver:\n")
    print(f"UPDATE users SET password_hash = '{hashed_password}' WHERE username = 'admin';")
    print("\n" + "="*60)
    print("\n✅ After running the SQL above, you can login as:")
    print("   - Leave username blank")
    print(f"   - Password: {password if not password.startswith(('$2b$', 'scrypt:')) else '(your password)'}")
    print("\n")

if __name__ == '__main__':
    set_admin_password()

