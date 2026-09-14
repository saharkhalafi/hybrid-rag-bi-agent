"""Safe SQL execution (read-only, time-boxed, row-capped) and chat history."""
import concurrent.futures
from typing import Optional

import pandas as pd
from langchain_core.chat_history import InMemoryChatMessageHistory
from sqlalchemy import text

from src.config import MAX_RESULT_ROWS, POSTGRES_HISTORY_URL, SQL_TIMEOUT_SECONDS, logger
from src.db.engine import get_engine
from src.observability.telemetry import log_event


def safe_execute(sql: str, timeout: int = SQL_TIMEOUT_SECONDS) -> Optional[pd.DataFrame]:
    """Execute a firewall-approved SELECT. Returns None on execution error/timeout."""
    if not sql or not sql.strip():
        return pd.DataFrame()

    sql = sql.strip().rstrip(";")

    def _run() -> pd.DataFrame:
        with get_engine().connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            return pd.read_sql_query(text(sql), conn)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            df = executor.submit(_run).result(timeout=timeout)
        if len(df) > MAX_RESULT_ROWS:
            df = df.head(MAX_RESULT_ROWS)
        return df
    except concurrent.futures.TimeoutError:
        log_event({"type": "sql_timeout", "sql": sql[:1000], "error": "timeout"})
        return None
    except Exception as exc:
        log_event({"type": "sql_error", "sql": sql[:500], "error": str(exc)[:500]})
        return None


def execute_for_error(sql: str) -> Optional[str]:
    """Run a query and return the database error message (None if it succeeded)."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text(f"SELECT * FROM ({sql.rstrip(';')}) AS _probe LIMIT 0"))
        return None
    except Exception as exc:
        return str(exc)[:600]


# ------------------------------------------------------------------ chat history
_memory_histories: dict[str, InMemoryChatMessageHistory] = {}


def get_history(session_id: str):
    """Return (history, connection). Falls back to in-memory when no history DB is set."""
    if POSTGRES_HISTORY_URL:
        try:
            import psycopg
            from langchain_postgres import PostgresChatMessageHistory

            conn = psycopg.connect(POSTGRES_HISTORY_URL)
            return PostgresChatMessageHistory("chat_history", session_id, sync_connection=conn), conn
        except Exception as exc:
            logger.warning("Postgres chat history unavailable, using memory: %s", exc)

    history = _memory_histories.setdefault(session_id, InMemoryChatMessageHistory())
    return history, None
