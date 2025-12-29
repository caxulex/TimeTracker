"""
Create Superadmin Script - Run this to create/update a superadmin user
Run inside backend container: python -m scripts.create_superadmin

Usage on production:
  docker exec timetracker-backend python -m scripts.create_superadmin
"""

import sys
sys.path.insert(0, ".")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.config import settings
from app.services.auth_service import AuthService

# Use sync URL for script
SYNC_DATABASE_URL = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")

# Superadmin credentials
SUPERADMIN_EMAIL = "shae@shaemarcus.com"
SUPERADMIN_PASSWORD = "admin123"
SUPERADMIN_NAME = "Shae Marcus"


def create_superadmin():
    """Create or update superadmin user"""
    engine = create_engine(SYNC_DATABASE_URL)
    
    with Session(engine) as session:
        # Check if user already exists
        result = session.execute(
            text("SELECT id, email, role FROM users WHERE email = :email"),
            {"email": SUPERADMIN_EMAIL}
        )
        existing = result.fetchone()
        
        password_hash = AuthService.hash_password(SUPERADMIN_PASSWORD)
        
        if existing:
            # Update existing user to superadmin
            session.execute(
                text("""
                    UPDATE users 
                    SET role = 'super_admin', 
                        password_hash = :password_hash,
                        is_active = true,
                        updated_at = NOW()
                    WHERE email = :email
                """),
                {"email": SUPERADMIN_EMAIL, "password_hash": password_hash}
            )
            session.commit()
            print(f"✅ Updated existing user to super_admin!")
        else:
            # Create new superadmin
            session.execute(
                text("""
                    INSERT INTO users (email, password_hash, name, role, is_active, created_at, updated_at)
                    VALUES (:email, :password_hash, :name, 'super_admin', true, NOW(), NOW())
                """),
                {
                    "email": SUPERADMIN_EMAIL,
                    "password_hash": password_hash,
                    "name": SUPERADMIN_NAME
                }
            )
            session.commit()
            print(f"✅ Superadmin account created!")
        
        print(f"\n📧 Superadmin Login Credentials:")
        print(f"   Email: {SUPERADMIN_EMAIL}")
        print(f"   Password: {SUPERADMIN_PASSWORD}")
        print(f"   Role: super_admin")
        print(f"\n🌐 Login at: https://timetracker.shaemarcus.com")


if __name__ == "__main__":
    create_superadmin()
