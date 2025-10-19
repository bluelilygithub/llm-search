"""
Admin Password Reset Script
This script resets the admin password by updating the .env file with a hashed password.
"""

import os
from werkzeug.security import generate_password_hash
import sys

def reset_admin_password(new_password):
    """Reset admin password to a new value"""
    
    # Hash the password
    hashed_password = generate_password_hash(new_password)
    
    print(f"New password hash generated: {hashed_password[:50]}...")
    
    # Path to .env file
    env_file = '.env'
    
    if not os.path.exists(env_file):
        print(f"❌ .env file not found. Creating new one...")
        with open(env_file, 'w') as f:
            f.write(f"AUTH_PASSWORD={hashed_password}\n")
        print(f"✅ Created .env file with new password")
        return
    
    # Read existing .env content
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    # Update or add AUTH_PASSWORD
    password_updated = False
    new_lines = []
    
    for line in lines:
        if line.startswith('AUTH_PASSWORD='):
            new_lines.append(f"AUTH_PASSWORD={hashed_password}\n")
            password_updated = True
            print(f"✅ Updated existing AUTH_PASSWORD in .env")
        else:
            new_lines.append(line)
    
    # If AUTH_PASSWORD wasn't found, add it
    if not password_updated:
        new_lines.append(f"\n# Admin password (hashed)\nAUTH_PASSWORD={hashed_password}\n")
        print(f"✅ Added AUTH_PASSWORD to .env")
    
    # Write back to .env
    with open(env_file, 'w') as f:
        f.writelines(new_lines)
    
    print(f"\n✅ Admin password has been reset successfully!")
    print(f"🔐 New password: {new_password}")
    print(f"\n⚠️  IMPORTANT: Restart your application for changes to take effect!")

if __name__ == '__main__':
    # The password you want to set
    NEW_PASSWORD = "SugarIsBad1$3%"
    
    print("="*60)
    print("     ADMIN PASSWORD RESET SCRIPT")
    print("="*60)
    print(f"\nSetting admin password to: {NEW_PASSWORD}")
    print("\nThis will update the AUTH_PASSWORD in your .env file with a secure hash.")
    
    confirm = input("\nAre you sure you want to proceed? (yes/no): ")
    
    if confirm.lower() in ['yes', 'y']:
        reset_admin_password(NEW_PASSWORD)
    else:
        print("\n❌ Password reset cancelled.")
        sys.exit(0)

