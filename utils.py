import uuid
import time
import re
import hashlib
import concurrent.futures
from typing import Dict, Any
from datetime import datetime

import streamlit as st
import pandas as pd
import psycopg
from sqlalchemy import text
from langchain_postgres import PostgresChatMessageHistory
import sqlglot
from sqlglot.expressions import Select

from config import (
    db, llm, llm_cache, logger,
    POSTGRES_HISTORY_URL
)


# ========================= HELPERS =========================
def get_cache_key(prompt: str, node: str, model: str = "gemini-2.5-flash") -> str:
    """Generate a stable cache key for LLM calls."""
    # Better normalization
    normalized = re.sub(r"\s+", " ", prompt.strip())
    key_string = f"{model}:{node}:{normalized}"
    return hashlib.sha256(key_string.encode()).hexdigest()

def ensure_state(state):
    state.setdefault("messages", [])
    state.setdefault("retry", 0)
    state.setdefault("error", None)
    return state


def merge_state(old, new):
    merged = dict(old)
    merged.update(new)
    return merged


def log_event(event: Dict[str, Any]):
    enriched = {
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": st.session_state.get("session_id"),
        **event
    }
    if "error" in enriched:
        enriched["level"] = "ERROR"
    st.session_state.telemetry.append(enriched)
    if len(st.session_state.telemetry) > 200:
        st.session_state.telemetry = st.session_state.telemetry[-200:]
    logger.info(enriched)


# ========================= LOGGING TO DB =========================
def log_llm_call(data: dict):
    """
    Production-grade logging for AI agent telemetry.
    Safely logs:
    - LLM calls
    - Retriever hits
    - SQL execution
    - Reflection retries
    - Chart/explanation generation
    """

    # =========================
    # DEFAULT SAFE VALUES
    # =========================
    safe_data = {
        "id": None,
        "session_id": None,
        "user_query": None,
        "node": None,
        "model": None,

        "latency_ms": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0,

        "success": True,
        "error": None,
        "cache_hit": False,

        # =========================
        # NEW ADVANCED FIELDS
        # =========================
        "query_type": None,
        "similarity_score": None,
        "template_id": None,
        "retrieval_latency_ms": None,

        "sql_query": None,
        "sql_execution_ms": None,
        "row_count": None,

        "retry_count": 0,
        "route_taken": None,

        "semantic_success": None,

        "chart_generated": False,
        "explanation_generated": False,
    }

    # overwrite defaults with incoming data
    safe_data.update(data)

    try:
        with db._engine.begin() as conn:

            conn.execute(
                text("""
                    INSERT INTO ai_request_logs (
                        id,
                        session_id,
                        user_query,
                        node,
                        model,

                        latency_ms,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        estimated_cost,

                        success,
                        error,
                        cache_hit,

                        query_type,
                        similarity_score,
                        template_id,
                        retrieval_latency_ms,

                        sql_query,
                        sql_execution_ms,
                        row_count,

                        retry_count,
                        route_taken,

                        semantic_success,

                        chart_generated,
                        explanation_generated

                    ) VALUES (

                        :id,
                        :session_id,
                        :user_query,
                        :node,
                        :model,

                        :latency_ms,
                        :prompt_tokens,
                        :completion_tokens,
                        :total_tokens,
                        :estimated_cost,

                        :success,
                        :error,
                        :cache_hit,

                        :query_type,
                        :similarity_score,
                        :template_id,
                        :retrieval_latency_ms,

                        :sql_query,
                        :sql_execution_ms,
                        :row_count,

                        :retry_count,
                        :route_taken,

                        :semantic_success,

                        :chart_generated,
                        :explanation_generated
                    )
                """),
                safe_data
            )

    except Exception as e:
        logger.error(
            f"Failed to log to ai_request_logs: {e}",
            exc_info=True
        )


# ========================= HISTORY =========================
def get_pg_conn():
    return psycopg.connect(POSTGRES_HISTORY_URL)


def get_history(session_id: str):
    conn = get_pg_conn()
    history = PostgresChatMessageHistory("chat_history", session_id, sync_connection=conn)
    return history, conn


# ========================= SQL EXECUTION =========================
def safe_execute(sql: str, timeout=15, max_rows=500):
    if not sql or not sql.strip():
        return pd.DataFrame()
    
    sql = sql.strip().rstrip(";")
    
    # More robust LIMIT handling
    if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        sql = f"{sql} LIMIT {max_rows}"
    elif re.search(r"\bLIMIT\s+\d+", sql, re.IGNORECASE):
        # Optionally cap the limit
        pass

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                pd.read_sql_query, 
                text(sql), 
                db._engine
            )
            return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        log_event({"type": "sql_timeout", "sql": sql[:1000]})
        return None
    except Exception as e:
        log_event({"type": "sql_error", "sql": sql[:500], "error": str(e)})
        return None


# ========================= LLM CALL =========================
# ========================= LLM CALL =========================
def call_llm(prompt: str, node: str):

    start = time.time()

    # === IMPROVED CACHE KEY ===
    cache_key = get_cache_key(prompt, node)

    # =========================
    # CACHE HIT
    # =========================
    if cache_key in llm_cache:
        log_llm_call({
            "id": str(uuid.uuid4()),
            "session_id": st.session_state.get("session_id"),
            "user_query": prompt[:500],
            "node": node,
            "model": "gemini-2.5-flash",
            "latency_ms": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": 0,
            "success": True,
            "error": None,
            "cache_hit": True
        })
        return llm_cache[cache_key]

    # =========================
    # REAL LLM CALL
    # =========================
    try:
        response = llm.invoke(prompt)
        content = response.content

        latency_ms = round((time.time() - start) * 1000, 2)

        # === IMPROVED TOKEN ESTIMATION ===
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            prompt_tokens = len(enc.encode(prompt))
            completion_tokens = len(enc.encode(content))
        except ImportError:
            # Fallback to your original method
            prompt_tokens = int(len(prompt.split()) * 1.3)
            completion_tokens = int(len(content.split()) * 1.3)

        total_tokens = prompt_tokens + completion_tokens

        estimated_cost = round((total_tokens / 1_000_000) * 0.30, 6)

        # SAVE TO CACHE
        llm_cache[cache_key] = content

        log_llm_call({
            "id": str(uuid.uuid4()),
            "session_id": st.session_state.get("session_id"),
            "user_query": prompt[:180],
            "node": node,
            "model": "gemini-2.5-flash",
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost": estimated_cost,
            "success": True,
            "error": None,
            "cache_hit": False
        })

        return content

    except Exception as e:
        # ... your existing error logging ...
        log_llm_call({
            "id": str(uuid.uuid4()),
            "session_id": st.session_state.get("session_id"),
            "user_query": prompt[:180],
            "node": node,
            "model": "gemini-2.5-flash",
            "latency_ms": round((time.time() - start) * 1000, 2),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": 0,
            "success": False,
            "error": str(e),
            "cache_hit": False
        })
        raise e


# ========================= SQL FIREWALL =========================
def sql_firewall(sql: str) -> tuple[bool, str]:
    try:
        parsed = sqlglot.parse_one(sql, read="postgres")
        
        if not isinstance(parsed, Select):
            return False, "Only SELECT statements are allowed"
        
        if ";" in sql.strip().rstrip(";").strip():
            # More robust multi-statement check
            statements = sqlglot.transpile(sql, read="postgres", write="postgres")
            if len(statements) > 1:
                return False, "Multi-statement queries are blocked"
        
        # Get all table references
        tables = {t.name.lower() for t in parsed.find_all(sqlglot.exp.Table)}
        allowed_tables = {"orders"}
        
        if not tables.issubset(allowed_tables):
            unauthorized = tables - allowed_tables
            return False, f"Unauthorized tables: {unauthorized}"
        
        # Optional: Block dangerous functions
        dangerous = {"exec", "execute", "format", "copy", "lo_import"}
        for func in parsed.find_all(sqlglot.exp.Anonymous):
            if func.this.lower() in dangerous:
                return False, f"Blocked function: {func.this}"
                
        return True, "OK"
        
    except Exception as e:
        return False, f"Parse error: {str(e)}"
