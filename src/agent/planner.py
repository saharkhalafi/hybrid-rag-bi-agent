"""Gemini analytical planner: structured JSON only, never SQL."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from src.llm.gemini import call_llm

ALLOWED_TYPES = {
    "period_comparison", "driver_analysis", "volume_vs_value",
    "dimension_comparison", "causal_change",
}
ALLOWED_METRICS = {"revenue", "orders", "quantity", "aov", "discount"}
ALLOWED_DIMENSIONS = {"city", "brand", "category", "product", "gender"}
ALLOWED_OPS = {
    "fetch", "percentage_change", "difference", "ratio",
    "rank", "sort", "dimension_breakdown",
}
MAX_STEPS = 8
ID_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,40}$")


class PlanError(ValueError):
    pass


METRIC_ALIAS = {"sales": "revenue", "sale": "revenue", "order_count": "orders", "aov_value": "aov"}
DIM_ALIAS = {
    "brand_name": "brand", "brands": "brand", "cities": "city",
    "category_level1": "category", "categories": "category",
    "order_items_name": "product", "products": "product",
}


def _extract_json(raw: str) -> dict:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise PlanError("planner did not return JSON")
    blob = text[start:end + 1]
    blob = blob.replace("“", '"').replace("”", '"')
    blob = re.sub(r",\s*}", "}", blob)
    blob = re.sub(r",\s*]", "]", blob)
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        try:
            return json.loads(blob.replace("'", '"'))
        except json.JSONDecodeError as exc:
            raise PlanError(f"invalid planner JSON: {exc}") from exc


def _clean_step(raw: dict, seen: set[str]) -> dict:
    if not isinstance(raw, dict):
        raise PlanError("step is not an object")
    sid = str(raw.get("id") or "").strip()
    if not ID_RE.match(sid) or sid in seen:
        raise PlanError(f"invalid or duplicate step id: {sid!r}")
    seen.add(sid)

    step: Dict[str, Any] = {"id": sid}
    metric = raw.get("metric")
    if metric is not None:
        metric = str(metric).strip().lower()
        metric = METRIC_ALIAS.get(metric, metric)
        if metric not in ALLOWED_METRICS:
            raise PlanError(f"unsupported metric: {metric}")
        step["metric"] = metric

    if raw.get("period"):
        step["period"] = str(raw["period"]).strip()[:40]
    if raw.get("dimension"):
        dim = str(raw["dimension"]).strip().lower()
        dim = DIM_ALIAS.get(dim, dim)
        if dim not in ALLOWED_DIMENSIONS:
            raise PlanError(f"unsupported dimension: {dim}")
        step["dimension"] = dim
    if raw.get("dimensions"):
        dims = [DIM_ALIAS.get(str(d).strip().lower(), str(d).strip().lower()) for d in raw["dimensions"]]
        if any(d not in ALLOWED_DIMENSIONS for d in dims):
            raise PlanError(f"unsupported dimensions: {dims}")
        step["dimensions"] = dims[:3]
    if raw.get("operation"):
        op = str(raw["operation"]).strip().lower()
        if op not in ALLOWED_OPS:
            raise PlanError(f"unsupported operation: {op}")
        step["operation"] = op
    if raw.get("inputs"):
        step["inputs"] = [str(x) for x in raw["inputs"][:4]]
    if raw.get("top_n") is not None:
        try:
            n = int(raw["top_n"])
            if 1 <= n <= 50:
                step["top_n"] = n
        except (TypeError, ValueError):
            pass
    if raw.get("question"):
        step["question"] = str(raw["question"]).strip()[:240]
    return step


def validate_plan(data: dict) -> dict:
    if not isinstance(data, dict):
        raise PlanError("plan is not an object")
    analysis_type = str(data.get("analysis_type") or "period_comparison").strip()
    if analysis_type not in ALLOWED_TYPES:
        analysis_type = "period_comparison"
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise PlanError("plan has no steps")
    if len(raw_steps) > MAX_STEPS:
        raw_steps = raw_steps[:MAX_STEPS]

    seen: set[str] = set()
    steps = [_clean_step(s, seen) for s in raw_steps]
    ids = [s["id"] for s in steps]
    for i, step in enumerate(steps):
        earlier = set(ids[:i])
        missing = [inp for inp in (step.get("inputs") or []) if inp not in earlier]
        if missing:
            raise PlanError(f"step {step['id']} inputs are not earlier steps: {missing}")
    return {"analysis_type": analysis_type, "steps": steps}


def fallback_plan(question: str, analysis_type: Optional[str] = None) -> dict:
    """Tiny deterministic skeleton if Gemini JSON is unusable. Still executed via SQL firewall."""
    from src.agent.complexity import _months
    from src.agent.routing import _norm, _tokens

    months = _months(question)
    current = months[0] if months else "شهریور"
    previous = months[1] if len(months) > 1 else "مرداد"
    kind = analysis_type or "period_comparison"
    toks = set(_tokens(_norm(question)))
    if kind == "volume_vs_value":
        return validate_plan({
            "analysis_type": kind,
            "steps": [
                {"id": "current_revenue", "metric": "revenue", "period": current, "operation": "fetch"},
                {"id": "previous_revenue", "metric": "revenue", "period": previous, "operation": "fetch"},
                {"id": "current_orders", "metric": "orders", "period": current, "operation": "fetch"},
                {"id": "previous_orders", "metric": "orders", "period": previous, "operation": "fetch"},
                {"id": "revenue_change", "operation": "percentage_change", "inputs": ["current_revenue", "previous_revenue"]},
                {"id": "orders_change", "operation": "percentage_change", "inputs": ["current_orders", "previous_orders"]},
                {"id": "current_aov", "operation": "ratio", "inputs": ["current_revenue", "current_orders"]},
                {"id": "previous_aov", "operation": "ratio", "inputs": ["previous_revenue", "previous_orders"]},
            ],
        })
    dims = []
    if toks & {"شهر", "شهرها", "شهرهای", "city", "cities"}:
        dims.append("city")
    if toks & {"برند", "برندها", "برندهای", "brand", "brands"}:
        dims.append("brand")
    if toks & {"دسته", "کتگوری", "category"}:
        dims.append("category")
    if not dims:
        dims = ["city"]
    return validate_plan({
        "analysis_type": kind if kind in ALLOWED_TYPES else "period_comparison",
        "steps": [
            {"id": "current_period", "metric": "revenue", "period": current, "operation": "fetch"},
            {"id": "previous_period", "metric": "revenue", "period": previous, "operation": "fetch"},
            {"id": "change", "operation": "percentage_change", "inputs": ["current_period", "previous_period"]},
            {"id": "drivers", "operation": "dimension_breakdown", "dimensions": dims,
             "inputs": ["current_period", "previous_period"]},
        ],
    })


def create_plan(question: str, analysis_type: Optional[str] = None) -> dict:
    hint = analysis_type or "period_comparison"
    prompt = f"""You are a BI analyst planner. Return STRICT JSON only (no SQL, no markdown).

The user question needs several analytical operations. Describe WHAT to compute.
Existing SQL generation will turn each fetch step into a query.

Schema of orders: revenue, quantity, order_id, city, brand_name, category_level1, order_date.
Jalali months: فروردین=Apr ... مرداد=Aug, شهریور=Sep.

Allowed analysis_type: period_comparison, driver_analysis, volume_vs_value, causal_change
Allowed metric: revenue, orders, quantity, aov, discount
Allowed dimensions: city, brand, category, product, gender
Allowed operation: fetch, percentage_change, difference, ratio, rank, sort, dimension_breakdown

Rules:
- At most 8 steps.
- Fetch steps get metric + optional period + optional dimension. Do not put arithmetic in fetch steps.
- percentage_change / difference / ratio / rank / sort are computed in Python from earlier step ids.
- For "why did sales drop" fetch current and previous revenue, a percentage_change, then dimension_breakdown on city and brand.
- For volume vs AOV: fetch orders and revenue for each period; AOV and percentages are Python (ratio / percentage_change).
- If the question does not name months, use شهریور as current and مرداد as previous.
- Do not emit SQL.
- Suggested type: {hint}

JSON shape:
{{"analysis_type": "...", "steps": [
  {{"id": "current_period", "metric": "revenue", "period": "شهریور", "operation": "fetch"}},
  {{"id": "previous_period", "metric": "revenue", "period": "مرداد", "operation": "fetch"}},
  {{"id": "change", "operation": "percentage_change", "inputs": ["current_period", "previous_period"]}},
  {{"id": "drivers", "operation": "dimension_breakdown", "dimensions": ["city", "brand"], "inputs": ["current_period", "previous_period"]}}
]}}

User question: {question}
"""
    last_error = None
    try:
        raw = call_llm(prompt, "planner")
        return validate_plan(_extract_json(raw))
    except (PlanError, json.JSONDecodeError) as exc:
        last_error = str(exc)
    raise PlanError(last_error or "planner failed")
