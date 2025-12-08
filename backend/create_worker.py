import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models import User
from app.services.auth_service import auth_service

async def create_worker():
    async with async_session() as session:
        # Check existing users
        result = await session.execute(select(User))
        users = result.scalars().all()
        print("Existing users:")
        for u in users:
            print(f"  - Email: {u.email}, Role: {u.role}, Name: {u.name}")
        
        # Check if worker exists
        result = await session.execute(select(User).where(User.email == "worker@timetracker.com"))
        worker = result.scalar_one_or_none()
        
        if not worker:
            # Create worker user
            worker = User(
                email="worker@timetracker.com",
                password_hash=auth_service.hash_password("worker123"),
                name="Demo Worker",
                role="member",
                is_active=True
            )
            session.add(worker)
            await session.commit()
            print("\n✅ Worker account created!")
        else:
            print("\n✅ Worker account already exists!")
        
        print("\n📧 Worker Login Credentials:")
        print("   Email: worker@timetracker.com")
        print("   Password: worker123")

if __name__ == "__main__":
    asyncio.run(create_worker())
