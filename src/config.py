"""Central configuration: environment, caches, thresholds, Gemini LLM factory."""
import logging
import os

import streamlit as st
from cachetools import TTLCache
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# ------------------------------------------------------------------ environment
DATABASE_URL = os.getenv("DATABASE_URL")
POSTGRES_HISTORY_URL = os.getenv("POSTGRES_HISTORY_URL")  # optional: chat history + audit log
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_LLM_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-2.5-flash")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.85"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
MAX_SQL_RETRIES = int(os.getenv("MAX_SQL_RETRIES", "2"))

# ------------------------------------------------------------------ security limits
MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", "500"))
SQL_TIMEOUT_SECONDS = int(os.getenv("SQL_TIMEOUT_SECONDS", "15"))
MAX_QUESTION_CHARS = int(os.getenv("MAX_QUESTION_CHARS", "500"))
MAX_SQL_CHARS = int(os.getenv("MAX_SQL_CHARS", "4000"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
ALLOWED_TABLES = {"orders"}

# ------------------------------------------------------------------ logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bi_agent")


def require_env(value: str | None, name: str) -> str:
    if value:
        return value
    st.error(f"{name} is missing")
    st.stop()
    raise RuntimeError(f"{name} is missing")


# ------------------------------------------------------------------ caches
sql_cache = TTLCache(maxsize=512, ttl=600)
query_cache = TTLCache(maxsize=200, ttl=300)
llm_cache = TTLCache(maxsize=150, ttl=900)
explain_cache = TTLCache(maxsize=300, ttl=1800)


def clear_caches() -> None:
    for cache in (sql_cache, query_cache, llm_cache, explain_cache):
        cache.clear()


# ------------------------------------------------------------------ Gemini LLM
_llm = None


def get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(
            model=GEMINI_LLM_MODEL,
            temperature=0,
            google_api_key=require_env(GEMINI_API_KEY, "GEMINI_API_KEY"),
            max_tokens=1800,
        )
    return _llm
