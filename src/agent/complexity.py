"""Deterministic detector for questions that need more than one analytical operation.

This is not an LLM call. Simple fact / ranking / single-period questions stay on the
existing FAISS → template-or-Gemini-SQL → firewall → Postgres path.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from src.agent.routing import GREGORIAN_MONTHS_EN, GREGORIAN_MONTHS_FA, _norm, _tokens
from src.db.schema import JALALI_TO_GREGORIAN

MONTH_TOKENS = (
    { _norm(m) for m in JALALI_TO_GREGORIAN }
    | { _norm(m) for m in GREGORIAN_MONTHS_FA }
    | { _norm(m) for m in GREGORIAN_MONTHS_EN }
)

CHANGE_RE = re.compile(
    r"کاهش|افزایش|افت|کم\s*شد|زیاد\s*شد|رشد کرد|decline|decrease|increase|drop|grew|growth"
)
CAUSAL_RE = re.compile(r"\bچرا\b|\bwhy\b|به\s*دلیل|علت")
DRIVER_RE = re.compile(r"تاثیر|تأثیر|عامل|سهم .*کاهش|contributor|driver|چه چیزی باعث")
COMPARE_RE = re.compile(r"مقایسه|نسبت به|در مقایسه|compare|versus|\bvs\b")
SHARE_OF_TOTAL_RE = re.compile(r"نسبت به\s*(کل|تمام|کل فروش)|share of total")
VOLUME_RE = re.compile(r"تعداد\s*(سفارش|سفارش‌ها|سفارشها|خرید)|order count|number of orders")
VALUE_RE = re.compile(r"ارزش\s*(سفارش|سفارش‌ها)|میانگین ارزش|aov|average order")
OR_RE = re.compile(r"\bیا\b|\bor\b")
MULTI_PART_RE = re.compile(r"و بگو|و همچنین|همچنین بگو|و نشان بده|و شهرهایی|و برند")
RANK_CHANGE_RE = re.compile(
    r"بیشترین (افت|کاهش|رشد|افزایش|تاثیر|تأثیر)|کمترین (افت|رشد)|most (drop|decline|growth|impact)"
)
DIM_TOKENS = {
    "شهر", "شهرها", "شهرهای", "city", "cities",
    "برند", "برندها", "برندهای", "brand", "brands",
    "دسته", "کتگوری", "category", "categories",
    "محصول", "محصولات", "product", "products",
}
MONTHLY_SERIES_RE = re.compile(r"ماهانه|monthly|هر ماه")


@dataclass
class ComplexityResult:
    is_complex: bool
    analysis_type: str | None = None
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"is_complex": self.is_complex, "analysis_type": self.analysis_type, "reasons": self.reasons}


def _months(question: str) -> List[str]:
    found = []
    for tok in _tokens(_norm(question)):
        if tok in MONTH_TOKENS and tok not in found:
            found.append(tok)
    return found


def detect_complexity(question: str) -> ComplexityResult:
    """Return whether `question` needs a multi-step plan (no LLM)."""
    q = _norm(question)
    reasons: List[str] = []
    months = _months(question)
    two_periods = len(months) >= 2
    change = bool(CHANGE_RE.search(q))
    causal = bool(CAUSAL_RE.search(q))
    drivers = bool(DRIVER_RE.search(q))
    compare = bool(COMPARE_RE.search(q)) and not bool(SHARE_OF_TOTAL_RE.search(q))
    volume_vs_value = bool(VOLUME_RE.search(q) and VALUE_RE.search(q) and OR_RE.search(q))
    multi_part = bool(MULTI_PART_RE.search(q))
    rank_change = bool(RANK_CHANGE_RE.search(q))
    dim = bool(set(_tokens(q)) & DIM_TOKENS)
    monthly_series = bool(MONTHLY_SERIES_RE.search(q)) and not two_periods

    # Strong signals: causal change, contribution-to-a-drop, volume vs AOV.
    if causal and change:
        reasons.append("causal_change")
    if drivers and (change or compare or two_periods):
        reasons.append("drivers")
    if volume_vs_value:
        reasons.append("volume_vs_value")

    # Two named periods become multi-step only when a second operation is present.
    # Plain "growth from May to June" stays on the single-SQL path (gold set).
    extra_op = causal or drivers or rank_change or multi_part or volume_vs_value or (dim and compare)
    if two_periods and extra_op:
        reasons.append("period_comparison")
    if compare and two_periods and (rank_change or dim or multi_part):
        reasons.append("compare_and_breakdown")
    if rank_change and (two_periods or change) and dim:
        reasons.append("ranking_plus_comparison")
    if multi_part and (two_periods or compare or change):
        reasons.append("multi_part")

    if monthly_series:
        reasons = [r for r in reasons if r != "period_comparison"]

    analysis_type = None
    if "volume_vs_value" in reasons:
        analysis_type = "volume_vs_value"
    elif "drivers" in reasons or "ranking_plus_comparison" in reasons:
        analysis_type = "driver_analysis"
    elif "causal_change" in reasons:
        analysis_type = "causal_change"
    elif reasons:
        analysis_type = "period_comparison"

    return ComplexityResult(bool(reasons), analysis_type, reasons)
