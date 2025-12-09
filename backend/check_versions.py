import asyncio
from app.database import engine
from sqlalchemy import text

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(text('SELECT * FROM alembic_version'))
        versions = list(result)
        print("Current versions in database:")
        for v in versions:
            print(f"  - {v[0]}")

asyncio.run(check())
