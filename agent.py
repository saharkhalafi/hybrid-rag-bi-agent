import re
import hashlib
from typing import TypedDict, List, Optional, Dict
 
import streamlit as st
import pandas as pd
from langgraph.graph import StateGraph, END
 
from config import (
    sql_cache, query_cache, explain_cache,
    get_detailed_schema
)
from utils import (
    ensure_state, merge_state, log_event,
    safe_execute, call_llm, sql_firewall
)
 
# FIX: guarded import — app still works if retriever files are missing
try:
    from retriever import retriever
    _RETRIEVER_AVAILABLE = retriever.is_available()
except Exception:
    retriever = None
    _RETRIEVER_AVAILABLE = False
 
 
# ========================= STATE =========================
class AgentState(TypedDict):
    messages: List
    sql: Optional[str]
    dataframe: Optional[pd.DataFrame]
    explanation: Optional[str]
    chart: Optional[Dict]
    retry: int
    error: Optional[str]
 
 
# ========================= CACHE KEY HELPERS =========================
def get_query_cache_key(question: str, session_id: str) -> str:
    normalized = re.sub(r"\s+", " ", question.lower().strip())
    return hashlib.md5(f"{session_id}:{normalized}".encode()).hexdigest()
 
 
def get_explain_cache_key(df: pd.DataFrame, is_persian: bool) -> str:
    preview = df.head(10).sort_index(axis=1).to_json(
        orient="records", date_format="iso"
    )
    return hashlib.md5(f"{is_persian}:{preview}".encode()).hexdigest()
 
 
# ========================= NODES =========================
 
def sql_node(state):
    state = ensure_state(state)
    messages = state.get("messages") or []

    if not messages:
        return merge_state(state, {
            "sql": None,
            "error": "No messages"
        })

    # =========================
    # NORMALIZE QUESTION (CRITICAL FOR PERSIAN + EMBEDDINGS)
    # =========================
    import ftfy

    question = str(messages[-1].content).strip()
    question = ftfy.fix_text(question)  # FIX: broken utf-8 like "Ù‡Ø§"

    session_id = st.session_state.get("session_id", "default")

    # =========================
    # L1 CACHE (SQL CACHE)
    # =========================
    q_key = get_query_cache_key(question, session_id)

    if q_key in query_cache:
        log_event({"type": "query_cache_hit"})
        return merge_state(state, {
            "sql": query_cache[q_key],
            "error": None,
            "route_taken": "cache"
        })

    schema = get_detailed_schema()

    # =========================
    # RETRIEVER PATH (RAG LAYER)
    # =========================
    retriever_used = False
    score = 0.0
    best_template = None

    if _RETRIEVER_AVAILABLE and retriever is not None:
        try:
            # IMPORTANT: E5 format already handled inside retriever
            score, best_template = retriever.get_best_match(question)

            log_event({
                "type": "retriever_check",
                "score": float(score),
                "template_id": best_template["id"] if best_template else None
            })

            # =========================
            # TEMPLATE HIT (FAST PATH)
            # =========================
            if score >= 0.85 and best_template:

                sql = best_template["sql"].strip().rstrip(";")

                ok, msg = sql_firewall(sql)

                if ok:
                    query_cache[q_key] = sql
                    retriever_used = True

                    log_event({
                        "type": "template_hit",
                        "score": float(score),
                        "template_id": best_template["id"]
                    })

                    return merge_state(state, {
                        "sql": sql,
                        "error": None,
                        "route_taken": "retriever",
                        "template_id": best_template["id"],
                        "similarity_score": float(score),
                        "retriever_used": True
                    })

        except Exception as e:
            log_event({
                "type": "retriever_error",
                "error": str(e)
            })

    # =========================
    # LLM PATH (FALLBACK)
    # =========================
    prompt = f"""
You are a PostgreSQL expert. Generate only a valid SELECT query.

{schema}

User Question: {question}

Think step by step: 1. What columns and tables do I need? 
2. Do I need aggregation (SUM, COUNT, AVG)? 
3. Do I need filtering, grouping, or ranking? 
4. Should I use date functions or conditions? 
Rules: 
- ONLY use table "orders" 
- Always use double quotes for columns 
- Always add LIMIT 
 Return ONLY the SQL query, no explanation.
"""

    raw = call_llm(prompt, "sql")

    sql = (
        raw.replace("```sql", "")
           .replace("```", "")
           .strip()
           .rstrip(";")
           .strip()
    )

    ok, msg = sql_firewall(sql)

    if not ok:
        return merge_state(state, {
            "sql": None,
            "error": msg,
            "route_taken": "blocked"
        })

    # =========================
    # CACHE FINAL SQL
    # =========================
    if sql and sql.lower().startswith("select"):
        query_cache[q_key] = sql

    return merge_state(state, {
        "sql": sql,
        "error": None,
        "route_taken": "llm",
        "retriever_used": retriever_used,
        "similarity_score": float(score),
        "template_id": best_template["id"] if best_template else None
    })
 
 
def exec_node(state):
    state = ensure_state(state)
    sql = state.get("sql")
 
    if not sql:
        return merge_state(state, {
            "dataframe": pd.DataFrame(),
            "error": "No SQL generated"
        })
 
    key = hashlib.md5(sql.strip().lower().encode()).hexdigest()
 
    if key in sql_cache:
        log_event({"type": "sql_cache_hit"})
        return merge_state(state, {
            "dataframe": sql_cache[key].copy(),
            "error": None
        })
 
    df = safe_execute(sql)
 
    # FIX: None = execution error (timeout/exception); empty df = valid empty result
    if df is None:
        return merge_state(state, {
            "dataframe": pd.DataFrame(),
            "error": "Execution failed"
        })
 
    # FIX: empty result is not an error — route to explain with no-data message
    if df.empty:
        return merge_state(state, {
            "dataframe": df,
            "error": None           # no error — explain will handle "no data"
        })
 
    if len(df) <= 400:
        sql_cache[key] = df.copy()
 
    return merge_state(state, {"dataframe": df, "error": None})
 
 
def chart_decision_node(state):
    df = state.get("dataframe")
 
    if df is None or df.empty or len(df) < 2 or len(df.columns) < 2:
        return {"chart": None}
 
    question = str(state["messages"][-1].content).lower()
    col0, col1 = df.columns[0], df.columns[1]
 
    top_keywords = [
        "پرفروش", "best seller", "top", "highest",
        "most", "ranking", "بیشترین"
    ]
    is_top = any(k in question for k in top_keywords)
 
    if is_top and len(df) <= 20:
        return {"chart": {
            "type": "bar", "x": col1, "y": col0,
            "orientation": "h", "title": "رتبه‌بندی برتر"
        }}
 
    if any(t in col0.lower() for t in ["date", "month", "year", "day"]):
        return {"chart": {
            "type": "line", "x": col0, "y": col1, "title": "روند زمانی"
        }}
 
    if len(df) <= 12:
        return {"chart": {
            "type": "bar", "x": col0, "y": col1, "title": "مقایسه"
        }}
 
    return {"chart": {"type": "histogram", "x": col1, "title": "توزیع"}}
 
 
def explain_node(state):
    state = ensure_state(state)
    df = state.get("dataframe")
 
    if df is None or df.empty:
        return {"explanation": "No data returned."}
 
    question = str(state["messages"][-1].content)
    is_persian = bool(re.search(r'[\u0600-\u06FF]', question))
 
    # ── FAST PATH 1: single scalar — zero LLM cost ───────────────────────────
    if df.shape == (1, 1):
        val = df.iloc[0, 0]
        if isinstance(val, (int, float)):
            text = f"نتیجه: {val:,.0f}" if is_persian else f"Result: {val:,.0f}"
        else:
            text = f"نتیجه: {val}" if is_persian else f"Result: {val}"
        return {"explanation": text}
 
    # ── FAST PATH 2: 2-col ranking/trend — zero LLM cost ────────────────────
    if df.shape[1] == 2 and len(df) <= 15:
        col1, col2 = df.columns
        try:
            tmp = df.copy()
            tmp[col2] = pd.to_numeric(tmp[col2], errors="coerce")
            tmp = tmp.dropna(subset=[col2])
            if not tmp.empty:
                top = tmp.nlargest(1, col2).iloc[0]
                if is_persian:
                    return {"explanation": f"{top[col1]} با {top[col2]:,.0f} بیشترین مقدار را دارد."}
                else:
                    return {"explanation": f"{top[col1]} leads with {top[col2]:,.0f}."}
        except Exception:
            pass
 
    # ── FAST PATH 3: small result — zero LLM cost ───────────────────────────
    if len(df) <= 6:
        return {"explanation": (
            f"{len(df)} ردیف داده دریافت شد." if is_persian
            else f"Returned {len(df)} rows."
        )}
 
    # ── LLM PATH: only complex results reach here ────────────────────────────
    cache_key = get_explain_cache_key(df, is_persian)
    if cache_key in explain_cache:
        return {"explanation": explain_cache[cache_key]}
 
    preview = df.head(10).to_string(index=False, max_colwidth=60)
 
    if is_persian:
        prompt = (
            f"داده‌های زیر را به صورت حرفه‌ای، کوتاه و مفید "
            f"(حداکثر ۲۰-۳۰ کلمه) به فارسی خلاصه کن. "
            f"تمرکز روی مهم‌ترین insight تجاری باشد:\n\n{preview}"
        )
    else:
        prompt = (
            f"Summarize the following data professionally in 1-2 clear sentences "
            f"(max 30 words). Focus on the most important business insight:\n\n{preview}"
        )
 
    explanation = call_llm(prompt, "explain")
    explain_cache[cache_key] = explanation
    return {"explanation": explanation}
 
 
def reflect_node(state):
    state = ensure_state(state)
    retry = state.get("retry", 0) + 1
 
    if retry >= 2:
        return merge_state(state, {
            "error": "Too many retries",
            "retry": retry,
            "sql": None
        })
 
    schema = get_detailed_schema()
 
    prompt = f"""Fix the following SQL query that failed.
 
User Question: {state["messages"][-1].content}
Failed SQL: {state.get("sql", "")}
Error: {state.get("error", "Unknown error")}
 
{schema}
 
Rules:
- Only table "orders"
- Use double quotes for columns
- Return ONLY the corrected SQL query
 
Corrected SQL:"""
 
    raw = call_llm(prompt, "sql_reflect")
    fixed_sql = raw.replace("```sql", "").replace("```", "").strip().rstrip(";").strip()
 
    return merge_state(state, {"sql": fixed_sql, "retry": retry, "error": None})
 
 
# ========================= ROUTERS =========================
 
def route_after_exec(state):
    """
    FIX: exec now has its own router so errors are caught immediately.
    Previously exec→chart was unconditional, making reflect unreachable.
    """
    if state.get("error"):
        retry = state.get("retry", 0)
        if retry < 2:
            return "reflect"
        return "explain"                    # max retries hit → explain
 
    df = state.get("dataframe")
    if df is None or df.empty:
        return "explain"                    # valid empty result → explain
 
    # Has data with 2+ cols → chart (chart→explain is always run after)
    if len(df.columns) >= 2 and len(df) >= 2:
        return "chart"
 
    return "explain"
 
 
def route_after_chart(state):
    """
    FIX: returns string keys mapped to END, not the END sentinel directly.
    Decides whether explain is needed after chart.
    """
    question = str(state["messages"][-1].content).lower()
    df = state.get("dataframe")
 
    explain_keywords = [
        "explain", "summary", "summarize", "insight", "why", "what is",
        "تحلیل", "خلاصه", "معنی", "چی شد", "گزارش", "توضیح", "بگو"
    ]
 
    if any(k in question for k in explain_keywords):
        return "explain"
 
    if df is not None and not df.empty:
        if len(df) > 10 or len(df.columns) > 4:
            return "explain"
 
    return "end"                            # FIX: string "end", not END object
 
 
def route_after_reflect(state):
    # FIX: return string "end" instead of END object
    if state.get("retry", 0) >= 2:
        return "end"
    if state.get("error"):
        return "end"
    return "exec"
 
 
# ========================= GRAPH =========================
workflow = StateGraph(AgentState)
 
workflow.add_node("sql",     sql_node)
workflow.add_node("exec",    exec_node)
workflow.add_node("reflect", reflect_node)
workflow.add_node("chart",   chart_decision_node)
workflow.add_node("explain", explain_node)
 
workflow.set_entry_point("sql")
 
workflow.add_edge("sql", "exec")
 
# FIX: exec now has its own conditional router (was unconditional exec→chart before)
workflow.add_conditional_edges(
    "exec",
    route_after_exec,
    {
        "reflect": "reflect",
        "chart":   "chart",
        "explain": "explain",
    }
)
 
# FIX: END mapped as string key "end"
workflow.add_conditional_edges(
    "chart",
    route_after_chart,
    {
        "explain": "explain",
        "end":     END,
    }
)
 
workflow.add_conditional_edges(
    "reflect",
    route_after_reflect,
    {
        "exec": "exec",
        "end":  END,
    }
)
 
workflow.add_edge("explain", END)
 
agent = workflow.compile()