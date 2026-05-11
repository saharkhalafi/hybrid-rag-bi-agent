import os
import logging
import streamlit as st
from dotenv import load_dotenv
from cachetools import TTLCache
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
POSTGRES_HISTORY_URL = os.getenv("POSTGRES_HISTORY_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not all([DATABASE_URL, POSTGRES_HISTORY_URL, GEMINI_API_KEY]):
    st.error("❌ Missing environment variables")
    st.stop()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================= CACHES =========================
sql_cache = TTLCache(maxsize=512, ttl=600)
query_cache = TTLCache(maxsize=200, ttl=300)
if "cache_warmed" not in st.session_state:
    query_cache["warm"] = "SELECT 1;"
    st.session_state.cache_warmed = True

llm_cache = TTLCache(maxsize=150, ttl=900)
explain_cache = TTLCache(maxsize=300, ttl=1800)

# ========================= DB + LLM =========================
@st.cache_resource
def init_db():
    return SQLDatabase.from_uri(DATABASE_URL, include_tables=["orders"])

db = init_db()

@st.cache_resource(ttl=14400)  # 4 hours
def get_detailed_schema():
    """Static schema - very fast, no database query"""
    return """Single flat table: "orders"

Columns: order_id, order_date, revenue, city, category_level1, category_level2, 
order_items_name, brand_name, ordered_qty, Gender, discount_amount, type

Rules:
- ONLY use table "orders"
- Always use double quotes for column names (e.g. "category_level1", "ordered_qty")
- Use exact values from data (Persian or English) - do not translate
- Always add LIMIT at the end"""

# ====================== Pre-warm Critical Caches ======================
@st.cache_resource
def warmup_caches():
    """Pre-warm important caches on app startup"""
    try:
        get_detailed_schema()
        logger.info("✅ Caches pre-warmed successfully")
    except Exception as e:
        logger.warning(f"Cache warmup failed: {e}")

if "caches_warmed" not in st.session_state:
    warmup_caches()
    st.session_state.caches_warmed = True

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    google_api_key=GEMINI_API_KEY,
    max_tokens=1800
)
