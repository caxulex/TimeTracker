# Alembic migration environment configuration

from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool, create_engine
import os

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.models import Base
target_metadata = Base.metadata

# Database URL - get from environment or use default
# Convert asyncpg URL to psycopg2 for Alembic migrations
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://timetracker:timetracker_secure_password@postgres:5432/time_tracker")
if "asyncpg" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


