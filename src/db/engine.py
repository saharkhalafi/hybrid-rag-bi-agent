"""Database engines.

Security layer: the analytics engine opens every session as READ ONLY with a
server-side statement timeout, so even if a query slipped past the firewall it
could not modify data or run forever. Writes (chat history, audit log) use a
separate connection string.
"""
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.config import DATABASE_URL, POSTGRES_HISTORY_URL, SQL_TIMEOUT_SECONDS, require_env

_analytics_engine: Engine | None = None
_write_engine: Engine | None = None


def get_engine() -> Engine:
    """Read-only analytics engine (PostgreSQL)."""
    global _analytics_engine
    if _analytics_engine is None:
        options = (
            "-c default_transaction_read_only=on "
            f"-c statement_timeout={SQL_TIMEOUT_SECONDS * 1000} "
            "-c idle_in_transaction_session_timeout=30000"
        )
        _analytics_engine = create_engine(
            require_env(DATABASE_URL, "DATABASE_URL"),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            connect_args={"options": options},
        )
    return _analytics_engine


def get_write_engine() -> Engine | None:
    """Engine for audit logging. None when POSTGRES_HISTORY_URL is not configured."""
    global _write_engine
    if not POSTGRES_HISTORY_URL:
        return None
    if _write_engine is None:
        url = POSTGRES_HISTORY_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        _write_engine = create_engine(url, pool_pre_ping=True)
    return _write_engine
