"""Routing helpers between the template fast-path and Gemini SQL generation.

A template is only trusted when the question does not ask for something the
template SQL cannot express. Embedding similarity is one signal; before a
retrieved template is used, `check_compatibility` verifies with deterministic
rules (question text + template metadata) that the template can satisfy:

  * value filters   - a specific city/brand/category/gender/status value
  * time filters    - month / year / relative date wording
  * top-N requests  - explicit "top 5" only when the template supports LIMIT rewriting
  * dimensions      - "per city", "which brand", "monthly" must be axes of the template
  * metrics/intent  - orders vs revenue vs customers vs quantity vs discount, avg/share/growth

ROUTING_MODE = "baseline" disables every check (pure similarity threshold) and is
used by scripts/evaluate.py to measure the value of the compatibility guard.
"""
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import sqlglot
from sqlglot import exp

from src.db.schema import JALALI_TO_GREGORIAN, get_column_values

ROUTING_MODE = os.getenv("ROUTING_MODE", "improved")  # "improved" | "baseline"


def set_routing_mode(mode: str) -> None:
    global ROUTING_MODE
    if mode not in {"improved", "baseline"}:
        raise ValueError(f"Unknown routing mode: {mode}")
    ROUTING_MODE = mode


def get_routing_mode() -> str:
    return ROUTING_MODE

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

GREGORIAN_MONTHS_FA = [
    "ژانویه", "فوریه", "مارس", "آوریل", "آپریل", "مه", "می", "ژوئن", "جون", "ژوئیه", "جولای",
    "اوت", "آگوست", "سپتامبر", "اکتبر", "نوامبر", "دسامبر",
]
GREGORIAN_MONTHS_EN = [
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul",
    "aug", "sep", "sept", "oct", "nov", "dec",
]
RELATIVE_TIME = [
    "امروز", "دیروز", "امسال", "سال جاری", "سال گذشته", "پارسال", "ماه جاری", "ماه گذشته", "ماه اخیر",
    "هفته گذشته", "هفته اخیر", "هفته جاری", "این ماه", "این هفته", "اخیر", "روز گذشته",
    "today", "yesterday", "this year", "last year", "this month", "last month", "last week",
    "this week", "recent", "past", "ytd", "q1", "q2", "q3", "q4",
]
GENDER_WORDS = {"زن", "زنان", "زنانه", "مرد", "مردان", "مردانه", "دخترانه", "پسرانه", "بچه گانه",
                "female", "male", "women", "men", "woman", "man", "girls", "boys", "kids"}
STATUS_WORDS = {"کامل", "تکمیل", "تحویل", "لغو", "مرجوع", "complete", "completed", "delivered", "cancelled", "canceled", "returned"}
TOP_WORDS = ["تاپ", "برتر", "بهترین", "بیشترین", "پرفروش", "top", "best", "highest", "most", "largest", "first"]
STOP_TOKENS = {"top", "best", "sales", "sale", "the", "and", "for", "with", "by", "of", "in", "به", "از", "در", "و", "با",
               "را", "که", "هر", "کل", "چقدر", "چقدره", "چند", "نشان", "بده", "مجموع", "فروش", "درآمد", "تعداد"}


@dataclass
class FilterSignals:
    entities: Dict[str, List[str]] = field(default_factory=dict)  # column -> matched values
    dates: List[str] = field(default_factory=list)
    gender: List[str] = field(default_factory=list)
    status: List[str] = field(default_factory=list)

    @property
    def any(self) -> bool:
        return bool(self.entities or self.dates or self.gender or self.status)

    def describe(self) -> str:
        parts = [f"{col}={vals}" for col, vals in self.entities.items()]
        if self.dates:
            parts.append(f"date={self.dates}")
        if self.gender:
            parts.append(f"gender={self.gender}")
        if self.status:
            parts.append(f"status={self.status}")
        return "; ".join(parts)


def _norm(text: str) -> str:
    text = text.translate(PERSIAN_DIGITS).replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def _tokens(text: str) -> List[str]:
    return re.findall(r"[\w\u0600-\u06FF]+", text)


_template_vocab: set | None = None


def _template_vocabulary() -> set:
    """Tokens used in template example questions. brand_name/category_level2 contain noisy values
    ('vip', 'Different', 'روزانه', ...) that collide with ordinary question words; any token that
    appears in the curated example questions is never treated as an entity literal."""
    global _template_vocab
    if _template_vocab is None:
        from src.rag.templates import SQL_TEMPLATES

        vocab: set = set()
        for t in SQL_TEMPLATES:
            for q in [t.get("description", "")] + list(t.get("example_questions") or []):
                vocab.update(_tokens(_norm(q)))
        _template_vocab = vocab
    return _template_vocab


def detect_filters(question: str) -> FilterSignals:
    q = _norm(question)
    tokens = _tokens(q)
    token_set = set(tokens)
    signals = FilterSignals()

    # dates
    if re.search(r"\b(19|20)\d{2}\b", q):
        signals.dates.append(re.search(r"\b(19|20)\d{2}\b", q).group(0))
    for m in list(JALALI_TO_GREGORIAN) + GREGORIAN_MONTHS_FA:
        if _norm(m) in token_set:
            signals.dates.append(m)
    for m in GREGORIAN_MONTHS_EN:
        if m in token_set:
            signals.dates.append(m)
    for phrase in RELATIVE_TIME:
        if (" " in phrase and phrase in q) or (" " not in phrase and phrase in token_set):
            signals.dates.append(phrase)

    # gender / status words
    signals.gender = sorted(w for w in GENDER_WORDS if (w in token_set) or (" " in w and w in q))
    signals.status = sorted(w for w in STATUS_WORDS if w in token_set)

    # database values
    values = get_column_values()
    vocab = _template_vocabulary()
    for col, vals in values.items():
        if col in {"status", "gender"}:
            continue
        hits: List[str] = []
        for value in vals:
            v = _norm(value)
            if len(v) < 3 or v in STOP_TOKENS or v in {"نامشخص", "other", "unknown", "متفرقه"}:
                continue
            if " " not in v and v in vocab:
                continue
            if " " in v:
                if v in q or all(part in token_set for part in v.split()):
                    hits.append(value)
            elif v in token_set:
                hits.append(value)
        if hits:
            signals.entities[col] = hits[:5]

    # "زنانه"/"مردانه" are both gender values and category_level1 values; keep both signals
    return signals


def template_covers(signals: FilterSignals, template_sql: str) -> bool:
    """A template covers the signals only if its SQL already contains every literal."""
    if not signals.any:
        return True
    sql_norm = _norm(template_sql)
    if signals.dates or signals.status:
        return False
    literals = [v for vals in signals.entities.values() for v in vals] + signals.gender
    return all(_norm(lit) in sql_norm for lit in literals)


def extract_top_n(question: str) -> int | None:
    q = _norm(question)
    if not any(w in q for w in TOP_WORDS):
        return None
    numbers = [int(n) for n in re.findall(r"\b(\d{1,3})\b", q)]
    numbers = [n for n in numbers if 1 <= n <= 200]
    if len(numbers) == 1:
        return numbers[0]
    return None


def apply_top_n(question: str, sql: str, template: Optional[Dict] = None) -> str:
    n = extract_top_n(question)
    if n is None:
        return sql
    if template is not None and template.get("supports_top_n") is False:
        return sql
    try:
        tree = sqlglot.parse_one(sql, read="postgres")
    except Exception:
        return sql
    if not isinstance(tree, exp.Select) or tree.args.get("order") is None:
        return sql
    tree.set("limit", exp.Limit(expression=exp.Literal.number(n)))
    return tree.sql(dialect="postgres")


# ---------------------------------------------------------------- intent signals
# Dimension nouns -> template dimension names. A noun only counts as a grouping axis
# when it carries a grouping marker ("هر شهر", "by city", "which brand", "top brands").
DIMENSION_NOUNS: Dict[str, str] = {
    "شهر": "city", "شهرها": "city", "شهرهای": "city", "city": "city", "cities": "city",
    "برند": "brand_name", "برندها": "brand_name", "برندهای": "brand_name", "brand": "brand_name", "brands": "brand_name",
    "دسته": "category_level1", "کتگوری": "category_level1", "category": "category_level1", "categories": "category_level1",
    "category_level1": "category_level1",
    "محصول": "order_items_name", "محصولات": "order_items_name", "کالا": "order_items_name", "کالاها": "order_items_name",
    "product": "order_items_name", "products": "order_items_name", "item": "order_items_name", "items": "order_items_name",
    "مشتری": "customer_name", "مشتریان": "customer_name", "customer": "customer_name", "customers": "customer_name",
    "جنسیت": "gender", "gender": "gender",
}
GROUPING_MARKERS_BEFORE = {"هر", "کدام", "تفکیک", "اساس", "برحسب", "per", "by", "each", "which", "every"}
GROUPING_MARKERS_AFTER = {"wise"}
RANKING_WORDS = {
    "تاپ", "برتر", "برترین", "بهترین", "بیشترین", "پرفروش", "پرسفارش", "بدترین", "کمترین", "محبوب", "وفادار", "پرتکرار",
    "پردرآمد", "رتبه", "مقایسه", "vip", "top", "best", "worst", "highest", "lowest", "most", "least", "popular",
    "frequent", "loyal", "ranking", "ranked", "rank", "compare", "leading", "biggest", "largest", "smallest",
    "performing", "selling", "spending", "profitable", "کم", "پایین", "بالاترین",
}
# Strict superlatives: asking for "the best/most X" is a ranking, which a time-ordered trend cannot answer.
SUPERLATIVE_WORDS = {"تاپ", "بهترین", "بیشترین", "کمترین", "بدترین", "بالاترین", "top", "best", "worst",
                     "highest", "lowest", "most", "least"}
TIME_DIMENSION_PATTERNS = {
    "month": r"ماهانه|ماه به ماه|هر ماه|monthly|per month|by month|each month|month over month|\bmom\b|month by month",
    "day": r"روزانه|هر روز|روز به روز|daily|per day|by day|each day",
    "year": r"سالانه|هر سال|سال ها|سالها|yearly|annual|per year|by year|each year",
    "weekday": r"روز هفته|روزهای هفته|weekday|weekdays|day of (the )?week",
}
METRIC_PATTERNS = {
    "orders": r"(تعداد|چند|شمار)\s*(کل\s*)?(سفارش|سفارشات|خرید)|پرسفارش|order count|number of (all )?orders|"
              r"how many (orders|purchases)|orders? per\b|count (all )?orders|order volume|most orders|repeat|frequent|"
              r"number of orders|orders? (by|in each)|who orders",
    "customers": r"(تعداد|چند)\s*(کل\s*)?(مشتری|نفر|خریدار)|مشتری(ان| های)? (یکتا|منحصر|متمایز)|unique (customers|buyers)|"
                 r"distinct customers|count of customers|how many .*customers|customers? count|different customers",
    "quantity": r"تعداد\s*(کالا|محصول|فروش|فروخته|واحد)|حجم فروش|quantity|units sold|\bqty\b",
    "discount": r"تخفیف|discount",
    "avg": r"میانگین|متوسط|average|\bmean\b|\bavg\b|typical",
    "share": r"سهم|درصد|share|percent|percentage|contribution|\bratio\b",
    "growth": r"رشد|growth|increase|month over month|\bmom\b",
}
MONEY_PATTERN = r"درآمد|revenue|مبلغ|ارزش|income|spending|spent"
SALES_PATTERN = r"فروش|sales|selling"
SUM_PATTERN = r"مجموع|جمع|total|\bsum\b|overall"
COUNT_LIKE = {"orders", "customers", "quantity", "discount"}


@dataclass
class IntentSignals:
    """Deterministic, lightweight description of what a question asks for."""
    filters: FilterSignals = field(default_factory=FilterSignals)
    dimensions: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)
    top_n: Optional[int] = None
    has_ranking_words: bool = False
    has_superlative: bool = False

    def describe(self) -> str:
        parts = []
        if self.filters.any:
            parts.append(self.filters.describe())
        if self.dimensions:
            parts.append(f"dims={self.dimensions}")
        if self.metrics:
            parts.append(f"metrics={self.metrics}")
        if self.top_n:
            parts.append(f"top_n={self.top_n}")
        if self.has_superlative:
            parts.append("superlative")
        return "; ".join(parts) or "none"

    def to_dict(self) -> Dict:
        return {
            "entities": self.filters.entities, "dates": self.filters.dates, "gender": self.filters.gender,
            "status": self.filters.status, "dimensions": self.dimensions, "metrics": self.metrics,
            "top_n": self.top_n, "superlative": self.has_superlative,
        }


def _is_ranking_token(tok: str) -> bool:
    return tok in RANKING_WORDS or tok.endswith("ترین")


def detect_dimensions(question: str) -> List[str]:
    q = _norm(question)
    tokens = _tokens(q)
    found: List[str] = []
    ranking_dim_taken = False
    for i, tok in enumerate(tokens):
        dim = DIMENSION_NOUNS.get(tok)
        if dim is None:
            continue
        before = tokens[max(0, i - 2):i]
        after = tokens[i + 1:i + 3]
        grouping = bool(set(before) & GROUPING_MARKERS_BEFORE) or bool(set(after) & GROUPING_MARKERS_AFTER)
        # A ranking word ("top", "پرفروش ترین", "محبوب") ranks exactly one axis: the first noun it touches.
        ranking = (not ranking_dim_taken) and any(_is_ranking_token(t) for t in before + after)
        if ranking:
            ranking_dim_taken = True
        if (grouping or ranking) and dim not in found:
            found.append(dim)
    for dim, pattern in TIME_DIMENSION_PATTERNS.items():
        if re.search(pattern, q) and dim not in found:
            found.append(dim)
    return found


def detect_metrics(question: str) -> List[str]:
    q = _norm(question)
    metrics = [m for m, pattern in METRIC_PATTERNS.items() if re.search(pattern, q)]
    if re.search(MONEY_PATTERN, q) or (re.search(SALES_PATTERN, q) and not (set(metrics) & COUNT_LIKE)):
        metrics.append("revenue")
    if "avg" not in metrics and re.search(SUM_PATTERN, q):
        metrics.append("sum")  # explicit total wording must not be answered by an average template
    return metrics


def detect_intent(question: str) -> IntentSignals:
    tokens = _tokens(_norm(question))
    return IntentSignals(
        filters=detect_filters(question),
        dimensions=detect_dimensions(question),
        metrics=detect_metrics(question),
        top_n=extract_top_n(question),
        has_ranking_words=any(_is_ranking_token(t) for t in tokens),
        has_superlative=any(t in SUPERLATIVE_WORDS or t.endswith("ترین") for t in tokens),
    )


# ---------------------------------------------------------------- compatibility
@dataclass
class CompatibilityResult:
    ok: bool
    reasons: List[str] = field(default_factory=list)
    signals: Optional[IntentSignals] = None

    @property
    def reason(self) -> Optional[str]:
        return "; ".join(self.reasons) if self.reasons else None


def _metric_satisfied(metric: str, template: Dict) -> bool:
    metrics = set(template.get("metrics") or [])
    intent = template.get("intent")
    if metric == "avg":
        return intent == "avg" or bool(metrics & {"revenue_per_unit"})
    if metric == "share":
        return intent in {"share", "growth"} or bool(metrics & {"share", "growth"})
    if metric == "growth":
        return intent == "growth" or "growth" in metrics
    if metric == "sum":
        return intent != "avg"
    return metric in metrics


def check_compatibility(question: str, template: Dict, signals: Optional[IntentSignals] = None) -> CompatibilityResult:
    """Decide whether a retrieved template can answer the question (deterministic rules)."""
    if ROUTING_MODE == "baseline":
        return CompatibilityResult(True, [], signals)

    signals = signals or detect_intent(question)
    reasons: List[str] = []
    template_dims = set(template.get("dimensions") or [])
    filters = signals.filters

    # 1. value filters: city/brand/category/... literals, dates, status
    if filters.dates:
        reasons.append(f"time filter not supported by template: {filters.dates}")
    if filters.status:
        reasons.append(f"status filter not supported by template: {filters.status}")
    if filters.entities:
        sql_norm = _norm(template.get("sql") or "")
        missing = {col: vals for col, vals in filters.entities.items()
                   if not all(_norm(v) in sql_norm for v in vals)}
        if missing:
            reasons.append(f"value filter not covered by template: {missing}")
    if filters.gender:
        # two or more gender words = a per-gender breakdown, which a gender-dimension template answers
        breakdown = "gender" in template_dims and len(set(filters.gender)) >= 2
        if not breakdown:
            reasons.append(f"gender filter not covered by template: {filters.gender}")

    # 2. explicit top-N only when the template's LIMIT can be rewritten meaningfully;
    #    a superlative ("best month") is a ranking that a time-ordered trend cannot answer
    if signals.top_n is not None and not template.get("supports_top_n"):
        reasons.append(f"top-{signals.top_n} requested but template does not support top-N")
    if signals.has_superlative and template.get("intent") == "trend":
        reasons.append("ranking (superlative) requested but template is a time trend")

    # 3. requested grouping axes must be axes of the template
    missing_dims = [d for d in signals.dimensions if d not in template_dims]
    if missing_dims:
        reasons.append(f"dimension(s) {missing_dims} not in template dimensions {sorted(template_dims)}")

    # 4. requested measures / aggregation intent must be produced by the template
    missing_metrics = [m for m in signals.metrics if not _metric_satisfied(m, template)]
    if missing_metrics:
        reasons.append(f"metric(s) {missing_metrics} not produced by template ({template.get('intent')}: "
                       f"{template.get('metrics')})")

    return CompatibilityResult(not reasons, reasons, signals)
