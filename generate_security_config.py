#!/usr/bin/env python3
"""
Security Configuration Generator for AI Knowledge Base

This script generates secure configurations for production deployment.
Run this script to generate secure SECRET_KEY and hashed AUTH_PASSWORD.
"""

import secrets
import os
from werkzeug.security import generate_password_hash
import sys

def generate_secret_key(length=64):
    """Generate a cryptographically secure secret key"""
    return secrets.token_hex(length)

def hash_password(password):
    """Generate a secure password hash"""
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

def main():
    print("🔐 AI Knowledge Base - Security Configuration Generator")
    print("=" * 60)
    
    # Generate SECRET_KEY
    secret_key = generate_secret_key()
    print(f"Generated SECRET_KEY: {secret_key}")
    
    # Get password from user
    print("\n📝 Admin Password Setup:")
    print("Choose an option:")
    print("1. Enter a custom admin password")
    print("2. Generate a random password")
    
    choice = input("Enter choice (1-2): ").strip()
    
    if choice == "2":
        # Generate random password
        password = secrets.token_urlsafe(16)
        print(f"Generated admin password: {password}")
        print("⚠️  IMPORTANT: Save this password securely!")
    elif choice == "1":
        # Get password from user
        password = input("Enter admin password: ").strip()
        if len(password) < 8:
            print("❌ Password must be at least 8 characters long")
            return
    else:
        print("❌ Invalid choice")
        return
    
    # Hash the password
    password_hash = hash_password(password)
    
    print("\n✅ Security Configuration Generated:")
    print("=" * 60)
    print("Add these to your .env file:")
    print()
    print(f"SECRET_KEY={secret_key}")
    print(f"AUTH_PASSWORD={password_hash}")
    print()
    print("🛡️  Security Notes:")
    print("- SECRET_KEY is used for session encryption")
    print("- AUTH_PASSWORD is securely hashed with PBKDF2")
    print("- Never share these values in version control")
    print("- Rotate SECRET_KEY periodically")
    print()
    
    # Offer to write to .env file
    write_env = input("Write to .env file? (y/n): ").strip().lower()
    if write_env == 'y':
        env_path = '.env'
        
        # Read existing .env if it exists
        existing_env = {}
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        existing_env[key.strip()] = value.strip()
        
        # Update with new values
        existing_env['SECRET_KEY'] = secret_key
        existing_env['AUTH_PASSWORD'] = password_hash
        
        # Write back to .env
        with open(env_path, 'w') as f:
            f.write("# AI Knowledge Base Configuration\n")
            f.write("# Generated on: " + str(__import__('datetime').datetime.now()) + "\n\n")
            
            f.write("# Database\n")
            f.write(f"DATABASE_URL={existing_env.get('DATABASE_URL', 'postgresql://username:password@localhost:5432/llm_search_db')}\n")
            f.write("DB_POOL_SIZE=10\n")
            f.write("DB_POOL_TIMEOUT=30\n")
            f.write("DB_POOL_RECYCLE=3600\n")
            f.write("DB_MAX_OVERFLOW=20\n\n")
            
            f.write("# AI Model APIs\n")
            for key in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'HUGGING_FACE_API_KEY', 'STABILITY_API_KEY']:
                f.write(f"{key}={existing_env.get(key, 'your_' + key.lower())}\n")
            f.write("\n")
            
            f.write("# Authentication & Security (GENERATED - DO NOT EDIT MANUALLY)\n")
            f.write(f"SECRET_KEY={secret_key}\n")
            f.write(f"AUTH_PASSWORD={password_hash}\n\n")
            
            f.write("# Cloud Storage (Optional)\n")
            for key in ['CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET']:
                f.write(f"{key}={existing_env.get(key, 'your_' + key.lower())}\n")
            f.write("\n")
            
            f.write("# Configuration\n")
            f.write(f"FLASK_CONFIG={existing_env.get('FLASK_CONFIG', 'production')}\n")
            f.write("FLASK_DEBUG=False\n")
        
        print(f"✅ Configuration written to {env_path}")
        print("🔒 Make sure to set appropriate file permissions:")
        print(f"   chmod 600 {env_path}")
    
    print("\n🚀 Next steps:")
    print("1. Set up your API keys in the .env file")
    print("2. Configure your database URL")
    print("3. Run: python app.py")
    print("4. Test authentication with your admin password")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Configuration generation cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)