from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy import engine_from_config
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

config = context.config
fileConfig(config.config_file_name)

# Ensure sqlalchemy.url is set from environment if provided (reads .env via app config)
import os
env_db = os.environ.get("DATABASE_URL")
# try loading from project .env if not in environment
if not env_db:
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as fh:
            for line in fh:
                if line.strip().startswith('DATABASE_URL='):
                    env_db = line.strip().split('=', 1)[1].strip().strip('"').strip("'")
                    break
if env_db:
    config.set_main_option("sqlalchemy.url", env_db)

from app.models import Base

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    def do_run_migrations(connection):
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    import asyncio

    async def run_async_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
