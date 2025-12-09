import asyncio
from app.database import engine
from sqlalchemy import text

async def create_table():
    async with engine.begin() as conn:
        # Create account_requests table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS account_requests (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                phone VARCHAR(50),
                job_title VARCHAR(255),
                department VARCHAR(255),
                message TEXT,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                submitted_at TIMESTAMP NOT NULL DEFAULT NOW(),
                reviewed_at TIMESTAMP,
                reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                admin_notes TEXT,
                ip_address VARCHAR(45),
                user_agent TEXT,
                CONSTRAINT status_check CHECK (status IN ('pending', 'approved', 'rejected'))
            )
        """))
        
        # Create indexes
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_account_requests_status ON account_requests(status)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_account_requests_email ON account_requests(email)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_account_requests_submitted ON account_requests(submitted_at DESC)
        """))
        
        print("✅ account_requests table created successfully!")

asyncio.run(create_table())
