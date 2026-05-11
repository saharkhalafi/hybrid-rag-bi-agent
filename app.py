import uuid
import streamlit as st
import pandas as pd
import plotly.express as px
from langchain_core.messages import HumanMessage

st.set_page_config(
    page_title="Enterprise BI Agent",
    layout="wide",
    page_icon="📊"
)

from config import logger
from utils import get_history
from agent import agent
from retriever import retriever

# ========================= SESSION STATE =========================
if "messages_ui" not in st.session_state:
    st.session_state.messages_ui = []

if "telemetry" not in st.session_state:
    st.session_state.telemetry = []

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


# ========================= RETRIEVER =========================
retriever_cached = retriever


# ========================= SAFE TEMPLATE ACCESS =========================
def get_templates():
    try:
        return getattr(retriever_cached, "templates", []) or []
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

    templates = get_templates()

    examples = []

    # safe extraction
    if templates:
        for t in templates[:8]:
            try:
                if t.get("example_questions"):
                    examples.append(t["example_questions"][0])
                elif t.get("description_en"):
                    examples.append(t["description_en"])
            except Exception:
                continue

    # fallback if retriever not ready
    if not examples:
        examples = [
            "What are total sales by category?",
            "Top products by revenue",
            "Sales by city",
            "Monthly revenue trend"
        ]

    for ex in examples:
        if st.button(ex, key=f"q_{hash(ex)}", use_container_width=True):
            st.session_state.pending_question = ex
            st.rerun()


# ========================= MAIN UI =========================
st.title("📊 Enterprise BI Agent")

for msg in st.session_state.messages_ui:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# chat input (must always be outside condition)
chat_input_value = st.chat_input("Ask your data...")


# resolve query
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

    history, conn = None, None

    try:
        history, conn = get_history(st.session_state.session_id)
        history.add_user_message(q)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):

                input_state = {
                    "messages": history.messages[-10:] + [
                        HumanMessage(content=q)
                    ],
                    "retry": 0,
                    "error": None,
                    "sql": None,
                    "dataframe": None,
                    "explanation": None,
                    "chart": None,
                }

                result = agent.invoke(
                    input_state,
                    config={"recursion_limit": 20}
                )

                # ========================= DEBUG =========================
                with st.expander("🔍 Debug Info", expanded=False):
                    st.code(result.get("sql", "No SQL"), language="sql")

                    if result.get("error"):
                        st.error(result.get("error"))

                    st.write("Rows:", len(result.get("dataframe", pd.DataFrame())))

                # ========================= DATA =========================
                df = result.get("dataframe")

                if df is not None and not df.empty:
                    st.dataframe(df, use_container_width=True, hide_index=True)

                    st.download_button(
                        "⬇️ Download CSV",
                        df.to_csv(index=False).encode(),
                        "result.csv",
                        mime="text/csv"
                    )

                # ========================= CHART =========================
                chart_config = result.get("chart")

                if chart_config and df is not None and not df.empty:
                    try:
                        fig = None

                        if chart_config["type"] == "bar":
                            fig = px.bar(
                                df,
                                x=chart_config["x"],
                                y=chart_config["y"],
                                orientation=chart_config.get("orientation", "v"),
                                title=chart_config.get("title", "")
                            )

                        elif chart_config["type"] == "line":
                            fig = px.line(
                                df,
                                x=chart_config["x"],
                                y=chart_config["y"],
                                title=chart_config.get("title", "")
                            )

                        elif chart_config["type"] == "histogram":
                            fig = px.histogram(
                                df,
                                x=chart_config["x"],
                                title=chart_config.get("title", "")
                            )

                        if fig:
                            st.plotly_chart(fig, use_container_width=True)

                    except Exception as chart_err:
                        logger.warning(f"Chart render failed: {chart_err}")

                # ========================= EXPLANATION =========================
                raw_explanation = result.get("explanation")

                explanation = (
                    str(raw_explanation).strip()
                    if raw_explanation is not None
                    else "Query executed successfully."
                )

                st.info(explanation)

                st.session_state.messages_ui.append({
                    "role": "assistant",
                    "content": explanation
                })

                history.add_ai_message(explanation)

    except Exception as e:
        logger.error(f"Agent Error: {e}", exc_info=True)
        st.error(f"❌ Error: {str(e)}")

    finally:
        if conn:
            conn.close()