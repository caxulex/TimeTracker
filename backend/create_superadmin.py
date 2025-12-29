"""
Script to create a superadmin user
Run with: python create_superadmin.py
"""
import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models import User
from app.services.auth_service import auth_service

async def create_superadmin():
    email = "shae@shaemarcus.com"
    password = "admin123"
    name = "Shae Marcus"
    
    async with async_session() as session:
        # Check if user already exists
        result = await session.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            # Update to superadmin if exists
            existing_user.role = "super_admin"
            existing_user.password_hash = auth_service.hash_password(password)
            existing_user.is_active = True
            await session.commit()
            print(f"\n✅ Updated existing user to super_admin!")
        else:
            # Create new superadmin user
            superadmin = User(
                email=email,
                password_hash=auth_service.hash_password(password),
                name=name,
                role="super_admin",
                is_active=True
            )
            session.add(superadmin)
            await session.commit()
            print(f"\n✅ Superadmin account created!")
        
        print("\n📧 Superadmin Login Credentials:")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        print(f"   Role: super_admin")

if __name__ == "__main__":
    asyncio.run(create_superadmin())
