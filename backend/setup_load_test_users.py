"""
Setup Test Users for Load Testing
Creates 100 test users with credentials loadtest1@test.com - loadtest100@test.com
Password for all: test123
"""

import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models import User
from app.services.auth import hash_password


async def create_test_users():
    """Create 100 test users for load testing"""
    async with async_session() as db:
        # Check how many test users already exist
        result = await db.execute(
            select(User).where(User.email.like('loadtest%@test.com'))
        )
        existing_users = result.scalars().all()
        
        if len(existing_users) >= 100:
            print(f"✅ {len(existing_users)} test users already exist. Skipping creation.")
            return
        
        print(f"Found {len(existing_users)} existing test users. Creating {100 - len(existing_users)} more...")
        
        existing_emails = {user.email for user in existing_users}
        created = 0
        
        for i in range(1, 101):
            email = f"loadtest{i}@test.com"
            
            if email in existing_emails:
                continue
            
            user = User(
                email=email,
                name=f"Load Test User {i}",
                password_hash=hash_password("test123"),
                role="worker",
                is_active=True
            )
            
            db.add(user)
            created += 1
            
            if created % 10 == 0:
                await db.commit()
                print(f"Created {created} users...")
        
        await db.commit()
        print(f"✅ Successfully created {created} test users!")
        print(f"📧 Emails: loadtest1@test.com - loadtest100@test.com")
        print(f"🔑 Password: test123")


async def cleanup_test_users():
    """Delete all test users (use after load testing)"""
    async with async_session() as db:
        result = await db.execute(
            select(User).where(User.email.like('loadtest%@test.com'))
        )
        users = result.scalars().all()
        
        if not users:
            print("No test users to delete.")
            return
        
        for user in users:
            await db.delete(user)
        
        await db.commit()
        print(f"✅ Deleted {len(users)} test users")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        print("🧹 Cleaning up test users...")
        asyncio.run(cleanup_test_users())
    else:
        print("👥 Creating test users for load testing...")
        asyncio.run(create_test_users())
