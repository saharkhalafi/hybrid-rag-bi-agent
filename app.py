import time
import uuid

import pandas as pd
import plotly.express as px
import streamlit as st
from langchain_core.messages import HumanMessage

st.set_page_config(page_title="Enterprise BI Agent", layout="wide", page_icon="📊")

from src.agent import agent  # noqa: E402
from src.config import RAG_SIMILARITY_THRESHOLD, logger  # noqa: E402
from src.db.executor import get_history  # noqa: E402
from src.observability.telemetry import get_events, log_event, summarize_observability  # noqa: E402
from src.rag.retriever import is_available, retriever  # noqa: E402
from src.security.input_guard import rate_limiter, validate_question  # noqa: E402

# ========================= SESSION STATE =========================
st.session_state.setdefault("messages_ui", [])
st.session_state.setdefault("telemetry", [])
st.session_state.setdefault("session_id", str(uuid.uuid4()))
st.session_state.setdefault("pending_question", None)

ROUTE_LABELS = {
    "retriever": "Template (no LLM SQL)",
    "llm": "Gemini SQL",
    "cache": "SQL cache",
    "blocked": "Blocked by security layer",
    "multi_step": "Multi-step analysis",
}


def get_templates():
    try:
        retriever.is_available()
        return getattr(retriever, "templates", []) or []
    except Exception:
        return []


# ========================= SIDEBAR =========================
with st.sidebar:
    st.markdown("## 🧠 Enterprise BI Agent")
    st.code(st.session_state.session_id[:8], language="markdown")

    if st.button("🆕 New Chat", type="primary", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages_ui = []
        st.session_state.pending_question = None
        st.rerun()

    st.divider()
    st.header("💡 Quick Questions")
    examples = [t["example_questions"][0] for t in get_templates()[:8] if t.get("example_questions")] or [
        "مجموع فروش کل چقدره؟", "تاپ 5 برند از نظر فروش", "فروش هر شهر (تاپ 10)", "روند فروش ماهانه را نشان بده",
    ]
    for ex in examples:
        if st.button(ex, key=f"q_{hash(ex)}", use_container_width=True):
            st.session_state.pending_question = ex
            st.rerun()

    st.divider()
    st.header("📡 Observability")
    metrics = summarize_observability()
    st.caption(f"FAISS ready: {is_available()} · threshold {RAG_SIMILARITY_THRESHOLD}")
    c1, c2 = st.columns(2)
    c1.metric("Latency", f"{metrics['last_latency_ms'] / 1000:.2f}s")
    c2.metric("Avg latency", f"{metrics['avg_latency_ms'] / 1000:.2f}s")
    c3, c4 = st.columns(2)
    c3.metric("Success", f"{metrics['success_rate']}%")
    c4.metric("LLM fallback", f"{metrics['llm_fallback_rate']}%")
    c5, c6 = st.columns(2)
    c5.metric("Template rate", f"{metrics['template_rate']}%")
    c6.metric("Tokens", metrics["total_tokens"])
    st.metric("Est. cost", f"${metrics['estimated_cost']:.5f}")

    with st.expander("Tool calls"):
        st.json(metrics["tool_calls"])
    if metrics["top_queries"]:
        st.subheader("Top queries")
        for question, count in metrics["top_queries"]:
            st.write(f"{count}× {question}")
    if metrics["recent_errors"]:
        st.subheader("Recent errors")
        for err in metrics["recent_errors"]:
            st.caption(str(err.get("error") or err.get("type")))


# ========================= MAIN UI =========================
st.title("📊 Enterprise BI Agent")

for msg in st.session_state.messages_ui:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

chat_input_value = st.chat_input("Ask your data...")

if st.session_state.pending_question:
    q = st.session_state.pending_question
    st.session_state.pending_question = None
elif chat_input_value:
    q = chat_input_value
else:
    q = None

# ========================= AGENT EXECUTION =========================
if q:
    st.session_state.messages_ui.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.markdown(q)

    guard = validate_question(q)
    if not guard.ok:
        log_event({"type": "input_blocked", "error": guard.reason})
        st.error(f"🚫 {guard.reason}")
        st.stop()
    if not rate_limiter.allow(st.session_state.session_id):
        log_event({"type": "rate_limited", "error": "rate limit"})
        st.warning("Too many requests, please wait a moment.")
        st.stop()

    history, conn = None, None
    try:
        history, conn = get_history(st.session_state.session_id)
        history.add_user_message(guard.question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                input_state = {
                    "messages": history.messages[-10:] + [HumanMessage(content=guard.question)],
                    "question": guard.question,
                    "retry": 0, "error": None, "sql": None, "dataframe": None, "explanation": None, "chart": None,
                }

                started = time.time()
                events_before = len(get_events())
                result = agent.invoke(input_state, config={"recursion_limit": 20})
                latency_ms = round((time.time() - started) * 1000, 2)

                df = result.get("dataframe")
                route_taken = result.get("route_taken")
                new_events = get_events()[events_before:]
                llm_events = [e for e in new_events if e.get("type") == "llm_call"]

                log_event({
                    "type": "query_complete",
                    "user_query": guard.question,
                    "route_taken": route_taken,
                    "template_id": result.get("template_id"),
                    "similarity_score": result.get("similarity_score"),
                    "retrieval_latency_ms": result.get("retrieval_latency_ms"),
                    "latency_ms": latency_ms,
                    "row_count": 0 if df is None else len(df),
                    "success": not bool(result.get("error")),
                    "error": result.get("error"),
                    "sql_query": result.get("sql"),
                    "chart_generated": bool(result.get("chart")),
                    "explanation_generated": bool(result.get("explanation")),
                    "total_tokens": sum(int(e.get("total_tokens") or 0) for e in llm_events),
                    "estimated_cost": sum(float(e.get("estimated_cost") or 0) for e in llm_events),
                })

                with st.expander("🔍 Debug Info", expanded=False):
                    st.code(result.get("sql") or "No SQL", language="sql")
                    st.write("Route:", ROUTE_LABELS.get(route_taken, route_taken))
                    st.write("Similarity:", result.get("similarity_score"))
                    st.write("Template:", result.get("template_id"))
                    if result.get("analysis_plan"):
                        st.write("Analysis plan:")
                        st.json(result["analysis_plan"])
                    if result.get("guard_reason"):
                        st.write("Guard:", result["guard_reason"])
                    st.write("Latency (ms):", latency_ms)
                    st.write("LLM calls:", len(llm_events))
                    if result.get("error"):
                        st.error(result.get("error"))
                    st.write("Rows:", 0 if df is None else len(df))

                if df is not None and not df.empty:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode("utf-8-sig"),
                                       "result.csv", mime="text/csv")

                chart_config = result.get("chart")
                if chart_config and df is not None and not df.empty:
                    try:
                        fig = None
                        if chart_config["type"] == "bar":
                            fig = px.bar(df, x=chart_config["x"], y=chart_config["y"],
                                         orientation=chart_config.get("orientation", "v"), title=chart_config.get("title", ""))
                        elif chart_config["type"] == "line":
                            fig = px.line(df, x=chart_config["x"], y=chart_config["y"], title=chart_config.get("title", ""))
                        elif chart_config["type"] == "histogram":
                            fig = px.histogram(df, x=chart_config["x"], title=chart_config.get("title", ""))
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
                    except Exception as chart_err:
                        logger.warning(f"Chart render failed: {chart_err}")

                explanation = str(result.get("explanation") or "Query executed successfully.").strip()
                (st.error if result.get("error") else st.info)(explanation)
                st.session_state.messages_ui.append({"role": "assistant", "content": explanation})
                history.add_ai_message(explanation)

    except Exception as e:
        logger.error(f"Agent Error: {e}", exc_info=True)
        st.error(f"❌ Error: {str(e)}")
    finally:
        if conn:
            conn.close()
