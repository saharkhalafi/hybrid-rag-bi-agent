"""In-process telemetry (works with or without a Streamlit session) + optional DB audit log."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.config import logger

_fallback_events: List[Dict[str, Any]] = []
_db_logging_enabled = True


def _session_state():
    try:
        import streamlit as st

        state = st.session_state
        state.get("session_id")  # raises outside a Streamlit run
        return state
    except Exception:
        return None


def current_session_id(default: str = "headless") -> str:
    state = _session_state()
    if state is None:
        return default
    return state.get("session_id") or default


def _events_store() -> List[Dict[str, Any]]:
    state = _session_state()
    if state is None:
        return _fallback_events
    if "telemetry" not in state:
        state["telemetry"] = []
    return state["telemetry"]


def get_events() -> List[Dict[str, Any]]:
    return list(_events_store())


def reset_events() -> None:
    _events_store().clear()


def log_event(event: Dict[str, Any]) -> None:
    enriched = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": current_session_id(),
        **event,
    }
    if enriched.get("error"):
        enriched["level"] = "ERROR"
    store = _events_store()
    store.append(enriched)
    if len(store) > 500:
        del store[:-500]
    logger.info(enriched)


def log_llm_call(data: Dict[str, Any]) -> None:
    """Audit row into ai_request_logs (only when a write DB is configured)."""
    global _db_logging_enabled
    if not _db_logging_enabled:
        return
    from src.db.engine import get_write_engine
    from sqlalchemy import text

    engine = get_write_engine()
    if engine is None:
        _db_logging_enabled = False
        return

    row = {
        "id": str(uuid.uuid4()), "session_id": None, "user_query": None, "node": None, "model": None,
        "latency_ms": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "estimated_cost": 0,
        "success": True, "error": None, "cache_hit": False, "query_type": None, "similarity_score": None,
        "template_id": None, "retrieval_latency_ms": None, "sql_query": None, "sql_execution_ms": None,
        "row_count": None, "retry_count": 0, "route_taken": None, "semantic_success": None,
        "chart_generated": False, "explanation_generated": False,
    }
    row.update(data)
    columns = ", ".join(row.keys())
    params = ", ".join(f":{k}" for k in row.keys())
    try:
        with engine.begin() as conn:
            conn.execute(text(f"INSERT INTO ai_request_logs ({columns}) VALUES ({params})"), row)
    except Exception as exc:
        _db_logging_enabled = False
        logger.warning("DB audit logging disabled: %s", str(exc)[:200])


def summarize_observability(events: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    events = events if events is not None else get_events()
    runs = [e for e in events if e.get("type") == "query_complete"]
    total = len(runs)

    def rate(pred) -> float:
        return round(100 * sum(1 for e in runs if pred(e)) / total, 1) if total else 0.0

    latencies = [float(e["latency_ms"]) for e in runs if e.get("latency_ms") is not None]
    counts: Dict[str, int] = {}
    for e in runs:
        q = (e.get("user_query") or "").strip()
        if q:
            counts[q] = counts.get(q, 0) + 1

    tool_calls = {
        "retriever_calls": sum(1 for e in events if e.get("type") == "retriever_check"),
        "template_hits": sum(1 for e in events if e.get("type") == "template_hit"),
        "guard_forced_llm": sum(1 for e in events if e.get("type") == "guard_forced_llm"),
        "llm_sql_calls": sum(1 for e in events if e.get("type") == "llm_call" and e.get("node") == "sql"),
        "llm_reflect_calls": sum(1 for e in events if e.get("type") == "llm_call" and e.get("node") == "sql_reflect"),
        "llm_explain_calls": sum(1 for e in events if e.get("type") == "llm_call" and e.get("node") == "explain"),
        "firewall_blocks": sum(1 for e in events if e.get("type") == "firewall_block"),
        "input_guard_blocks": sum(1 for e in events if e.get("type") == "input_blocked"),
        "sql_errors": sum(1 for e in events if e.get("type") in {"sql_error", "sql_timeout"}),
    }

    return {
        "total_queries": total,
        "success_rate": rate(lambda e: e.get("success")),
        "template_rate": rate(lambda e: e.get("route_taken") == "retriever"),
        "llm_fallback_rate": rate(lambda e: e.get("route_taken") == "llm"),
        "cache_rate": rate(lambda e: e.get("route_taken") == "cache"),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
        "last_latency_ms": latencies[-1] if latencies else 0.0,
        "total_tokens": sum(int(e.get("total_tokens") or 0) for e in runs),
        "estimated_cost": round(sum(float(e.get("estimated_cost") or 0) for e in runs), 6),
        "top_queries": sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:5],
        "recent_errors": [
            e for e in events
            if e.get("type") in {"sql_error", "sql_timeout", "retriever_error", "firewall_block", "input_blocked"}
            or (e.get("type") == "query_complete" and e.get("error"))
        ][-8:],
        "tool_calls": tool_calls,
    }
