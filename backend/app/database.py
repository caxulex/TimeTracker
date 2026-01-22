"""
Database connection and session management
"""

import logging
import time
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import event

from app.config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool,  # Disable connection pooling for development
    future=True,
)


# ============================================
# SLOW QUERY LOGGING
# ============================================
if settings.ENABLE_QUERY_LOGGING:
    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Record query start time"""
        conn.info.setdefault('query_start_time', []).append(time.time())
    
    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Log slow queries"""
        total_time = time.time() - conn.info['query_start_time'].pop(-1)
        total_ms = total_time * 1000
        
        if total_ms > settings.SLOW_QUERY_THRESHOLD_MS:
            # Truncate long queries for logging
            truncated_stmt = statement[:500] + "..." if len(statement) > 500 else statement
            logger.warning(
                f"SLOW QUERY ({total_ms:.2f}ms): {truncated_stmt}",
                extra={
                    "query_time_ms": total_ms,
                    "query": truncated_stmt,
                    "slow_query": True
                }
            )
        elif total_ms > 100:  # Log queries over 100ms at INFO level
            logger.info(
                f"Query time: {total_ms:.2f}ms",
                extra={"query_time_ms": total_ms}
            )


# Create async session factory
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Get database session"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables():
    """Create all database tables"""
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """Drop all database tables"""
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)