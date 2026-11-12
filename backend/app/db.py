from collections.abc import Iterator

from sqlalchemy.pool import NullPool
from sqlmodel import Session, create_engine

from app.config import DATABASE_URL


def _make_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # Supabase's transaction-mode pooler doesn't support prepared statements, and
    # serverless functions shouldn't hold their own pool, so let the pooler pool.
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    connect_args: dict = {"prepare_threshold": None}
    # Require TLS unless the URL explicitly chooses an sslmode (e.g. verify-full).
    if "sslmode=" not in url:
        connect_args["sslmode"] = "require"
    return create_engine(url, poolclass=NullPool, connect_args=connect_args)


engine = _make_engine(DATABASE_URL)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
