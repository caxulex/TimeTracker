import asyncio
from sqlalchemy import text
from app.database import async_session

async def add_role_column():
    async with async_session() as db:
        try:
            result = await db.execute(text('''
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'team_members' AND column_name = 'role'
            '''))
            exists = result.fetchone()
            
            if not exists:
                await db.execute(text('''
                    ALTER TABLE team_members 
                    ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'member'
                '''))
                await db.commit()
                print('Added role column to team_members')
            else:
                print('Role column already exists')
        except Exception as e:
            print(f'Error: {e}')

asyncio.run(add_role_column())
