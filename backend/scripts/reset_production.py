"""
Production Database Reset Script
Run with: python -m scripts.reset_production

This script clears all demo/test data and sets up a clean production environment
with only the admin account.
"""

import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, ".")

from app.config import settings
from app.services.auth_service import AuthService

# Use sync URL for script
SYNC_DATABASE_URL = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")


def reset_production():
    """Reset database to production state"""
    engine = create_engine(SYNC_DATABASE_URL)
    
    print("⚠️  WARNING: This will delete ALL data from the database!")
    print("This includes users, teams, projects, tasks, and time entries.")
    response = input("Are you sure you want to continue? (type 'YES' to confirm): ")
    
    if response != "YES":
        print("❌ Operation cancelled.")
        return
    
    with Session(engine) as session:
        print("\n🗑️  Deleting all data...")
        
        # Delete in correct order to avoid foreign key constraints
        tables = [
            'time_entries',
            'tasks',
            'projects',
            'team_members',
            'teams',
            'payroll_adjustments',
            'payroll_entries',
            'payroll_periods',
            'pay_rates',
            'user_invitations',
            'password_reset_tokens',
            'users'
        ]
        
        for table in tables:
            try:
                session.execute(text(f"DELETE FROM {table}"))
                print(f"  ✓ Cleared {table}")
            except Exception as e:
                print(f"  ⚠️  Could not clear {table}: {e}")
        
        session.commit()
        print("\n✅ All data deleted successfully")
        
        # Create admin user
        print("\n👤 Creating admin account...")
        admin_email = input("Admin email (default: admin@laboratoriodelolor.com): ").strip()
        if not admin_email:
            admin_email = "admin@laboratoriodelolor.com"
        
        admin_password = input("Admin password (default: Admin123!): ").strip()
        if not admin_password:
            admin_password = "Admin123!"
        
        admin_name = input("Admin name (default: Sistema Administrador): ").strip()
        if not admin_name:
            admin_name = "Sistema Administrador"
        
        from app.models import User
        admin = User(
            email=admin_email,
            password_hash=AuthService.hash_password(admin_password),
            name=admin_name,
            role="super_admin",
            is_active=True,
        )
        
        session.add(admin)
        session.commit()
        session.refresh(admin)
        
        print(f"\n✅ Admin user created successfully!")
        print(f"   Email: {admin.email}")
        print(f"   Password: {admin_password}")
        print(f"   ID: {admin.id}")
        print("\n⚠️  IMPORTANT: Save these credentials securely!")
        
        print("\n✨ Database is now ready for production use.")
        print("\nNext steps:")
        print("1. Login with the admin credentials")
        print("2. Create teams for your organization")
        print("3. Create workers and assign them to teams")
        print("4. Create projects for time tracking")


if __name__ == "__main__":
    reset_production()

