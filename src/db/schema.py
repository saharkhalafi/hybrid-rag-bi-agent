"""Canonical schema of the `orders` table plus data-aware prompt context."""
from functools import lru_cache
from typing import Dict, List

from sqlalchemy import text

from src.config import logger
from src.db.engine import get_engine

ORDERS_SCHEMA: Dict[str, Dict[str, str]] = {
    "table": "orders",
    "columns": {
        "item_id": "BIGINT",
        "order_id": "BIGINT",
        "status": "TEXT",
        "order_date": "DATE",
        "delivered_date": "DATE",
        "coupon_code": "TEXT",
        "city": "TEXT",
        "customer_id": "BIGINT",
        "customer_name": "TEXT",
        "category_level1": "TEXT",
        "category_level2": "TEXT",
        "gender": "TEXT",
        "order_items_name": "TEXT",
        "seller_type": "TEXT",
        "product_id": "BIGINT",
        "brand_name": "TEXT",
        "type": "TEXT",
        "ordered_qty": "INTEGER",
        "quantity": "INTEGER",
        "discount_amount": "NUMERIC",
        "revenue": "NUMERIC",
    },
}

SCHEMA_COLUMNS = set(ORDERS_SCHEMA["columns"].keys())

# Columns whose distinct values are loaded for filter detection and prompt hints.
FILTER_COLUMNS = ["city", "category_level1", "category_level2", "brand_name", "status", "gender", "seller_type"]
LOW_CARDINALITY_COLUMNS = ["status", "gender", "seller_type", "category_level1"]

# Persian (Jalali) month -> Gregorian month with the largest day overlap.
JALALI_TO_GREGORIAN = {
    "فروردین": "April", "اردیبهشت": "May", "خرداد": "June", "تیر": "July",
    "مرداد": "August", "شهریور": "September", "مهر": "October", "آبان": "November",
    "آذر": "December", "دی": "January", "بهمن": "February", "اسفند": "March",
}


@lru_cache(maxsize=1)
def get_column_values() -> Dict[str, List[str]]:
    """Distinct text values per filterable column (cached per process)."""
    values: Dict[str, List[str]] = {c: [] for c in FILTER_COLUMNS}
    try:
        engine = get_engine()
        with engine.connect() as conn:
            for col in FILTER_COLUMNS:
                rows = conn.execute(
                    text(
                        f'SELECT "{col}", COUNT(*) AS n FROM "orders" '
                        f'WHERE "{col}" IS NOT NULL GROUP BY "{col}" ORDER BY n DESC LIMIT 3000'
                    )
                ).fetchall()
                values[col] = [str(r[0]).strip() for r in rows if str(r[0]).strip()]
    except Exception as exc:  # DB unavailable: guard degrades to date/gender heuristics only
        logger.warning("Could not load column values for filter detection: %s", exc)
    return values


@lru_cache(maxsize=1)
def get_detailed_schema() -> str:
    values = get_column_values()

    def sample(col: str, n: int) -> str:
        items = values.get(col, [])[:n]
        return ", ".join(f"'{v}'" for v in items) if items else "(unavailable)"

    columns = "\n".join(f"{name:<20} {dtype}" for name, dtype in ORDERS_SCHEMA["columns"].items())
    jalali = ", ".join(f"{fa} -> {en}" for fa, en in JALALI_TO_GREGORIAN.items())

    return f"""You are querying a PostgreSQL database.

Table: "orders"  (one row per ordered item; an order can have several rows)

Columns:
{columns}

Data facts (use them, do not guess):
- status values: {sample('status', 5)}
- gender values (product target gender, can be combined): {sample('gender', 10)}
  -> for gender filters use "gender" LIKE '%value%'
- seller_type values: {sample('seller_type', 5)}
- category_level1 values: {sample('category_level1', 12)}
- category_level2 has {len(values.get('category_level2', []))} values, e.g. {sample('category_level2', 8)}
- most frequent cities: {sample('city', 12)}
- brand_name examples: {sample('brand_name', 8)}
- "order_date" is a Gregorian DATE. Count orders with COUNT(DISTINCT "order_id").
- Revenue is the "revenue" column; discounts are "discount_amount" (0 when no discount).
- "quantity" is the sold quantity; "ordered_qty" is the requested quantity.
- Persian (Jalali) month names map to Gregorian months: {jalali}

Rules:
1. ONLY use the "orders" table. Never invent tables or columns.
2. Quote identifiers with double quotes and use the exact column names above.
3. Persian values must stay exactly as stored (never translate or transliterate).
4. Prefer explicit column names over SELECT *.
5. Use PostgreSQL syntax (DATE_TRUNC, EXTRACT, BETWEEN, LIKE, CASE, window functions).
6. For month/year questions filter on "order_date" with an explicit date range.
7. For grouped/aggregated results do not add LIMIT unless the user asks for a top-N.
8. For raw row listings add LIMIT 100.
9. Read-only: SELECT statements only.
"""
