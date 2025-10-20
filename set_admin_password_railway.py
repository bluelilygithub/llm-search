"""
Set Admin Password for Railway Database
Run this AFTER the database migration is complete
"""

import os
from werkzeug.security import generate_password_hash
from sqlalchemy import create_engine, text

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL environment variable not set")
    print("Get it from Railway dashboard: Project → PostgreSQL → Connect → Database URL")
    exit(1)

# Your desired admin password
ADMIN_PASSWORD = "SugarIsBad1$3%"

# Generate hash
password_hash = generate_password_hash(ADMIN_PASSWORD)

print("🔐 Setting admin password...")
print(f"   Password: {ADMIN_PASSWORD}")
print(f"   Hash: {password_hash[:50]}...")

try:
    # Connect to database
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Update admin user password
        result = conn.execute(
            text("UPDATE users SET password_hash = :hash WHERE username = 'admin'"),
            {"hash": password_hash}
        )
        conn.commit()
        
        if result.rowcount > 0:
            print("✅ SUCCESS! Admin password updated")
            print(f"   Username: admin")
            print(f"   Password: {ADMIN_PASSWORD}")
        else:
            print("❌ ERROR: Admin user not found in database")
            print("   Make sure you ran the migration script first!")
            
except Exception as e:
    print(f"❌ ERROR: {str(e)}")
    print("   Make sure the database migration was run successfully")

