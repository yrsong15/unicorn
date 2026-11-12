from logging.config import fileConfig

from alembic import context
from sqlalchemy import text
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registers tables on SQLModel.metadata)
from app.db import engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()
            if connection.dialect.name == "postgresql":
                _enable_rls_everywhere(connection)


def _enable_rls_everywhere(connection) -> None:
    """Turn on Row Level Security for every table in the public schema.

    Supabase exposes public tables through its Data API; RLS with no policies
    blocks that API. Doing this after every migration covers alembic_version and
    any table added later. The backend connects as the table owner, which
    bypasses RLS, so the app is unaffected.
    """
    tables = connection.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity")
    ).scalars()
    for table in tables:
        connection.execute(text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))


run_migrations_online()
