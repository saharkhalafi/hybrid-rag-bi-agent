"""Streamlit presentation helpers. No agent/SQL/security logic."""
from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")

TIME_NAME_HINTS = (
    "date", "month", "year", "day", "week", "time", "period", "تاریخ", "ماه", "سال", "روز", "هفته",
)
SHARE_NAME_HINTS = ("share", "percent", "pct", "ratio", "سهم", "درصد")
GROWTH_NAME_HINTS = ("growth", "change", "delta", "diff", "pct_change", "رشد", "تغییر")
RANK_QUESTION_HINTS = (
    "پرفروش", "برتر", "بیشترین", "کمترین", "رتبه", "تاپ", "top", "best", "highest", "lowest",
    "ranking", "most", "least",
)
SHARE_QUESTION_HINTS = ("سهم", "درصد", "share", "percent", "proportion", "breakdown")
TIME_QUESTION_HINTS = ("روند", "ماهانه", "روزانه", "سالانه", "trend", "monthly", "daily", "over time")

COLUMN_LABELS = {
    "total_revenue": "Total Revenue",
    "revenue": "Revenue",
    "total_orders": "Orders",
    "order_count": "Orders",
    "unique_customers": "Customers",
    "avg_order_value": "Avg. Order Value",
    "avg_discount": "Avg. Discount",
    "total_qty": "Quantity",
    "quantity": "Quantity",
    "brand_name": "Brand",
    "category_level1": "Category",
    "order_items_name": "Product",
    "customer_name": "Customer",
    "city": "City",
    "gender": "Gender",
    "month": "Month",
    "year": "Year",
    "day": "Day",
    "dimension": "Dimension",
    "difference": "Difference",
    "pct_change": "Change %",
    "current": "Current",
    "previous": "Previous",
    "sum": "Value",
    "total_spent": "Total Spent",
    "total_discount": "Discount",
}

ANALYSIS_TYPE_LABELS = {
    "period_comparison": "Period comparison",
    "driver_analysis": "Driver analysis",
    "volume_vs_value": "Volume vs value",
    "dimension_comparison": "Dimension comparison",
    "causal_change": "Change analysis",
}

ROUTE_LABELS = {
    "retriever": "Template (no LLM SQL)",
    "llm": "Gemini SQL",
    "cache": "SQL cache",
    "blocked": "Blocked by security layer",
    "multi_step": "Multi-step analysis",
}

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Vazirmatn:wght@400;500;600;700&display=swap');

html, body, .stApp, textarea, input, .stMarkdown, .stCaption {
  font-family: "IBM Plex Sans", "Vazirmatn", sans-serif !important;
}
[data-testid="stHeader"] {
  background: #0B0B0C;
  border-bottom: 1px solid #2A2A2E;
}
.block-container {
  padding-top: 5rem;
  padding-bottom: 3.5rem;
  max-width: 1120px;
}
[data-testid="stSidebar"] {
  background: #0E0E10;
  border-right: 1px solid #2A2A2E;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
  position: static !important;
  line-height: 1.35 !important;
}
[data-testid="stMarkdownContainer"] a[href^="#"] {
  display: none !important;
}
.st-emotion-cache-1f95mb {
  font-size: 1.25rem !important;
}
.workspace-header { margin: 0 0 1.35rem 0; }
p.app-title {
  font-size: 2.35rem !important;
  font-weight: 600;
  letter-spacing: -0.03em;
  margin: 0 0 0.45rem 0;
  line-height: 1.2;
  color: #F5F5F6;
}
.app-sub {
  margin: 0;
  color: #A8A8B0;
  font-size: 0.95rem;
  line-height: 1.55;
  max-width: 46rem;
}
.side-label, .section-label {
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #8E8E96;
  margin: 0.85rem 0 0.5rem;
  line-height: 1.3;
}
.card {
  border: 1px solid #2A2A2E;
  background: #141416;
  border-radius: 12px;
  padding: 1rem 1.15rem;
  margin-bottom: 0.95rem;
}
.insight-card { font-size: 1.02rem; line-height: 1.75; color: #ECECEF; }
.insight-card.rtl, .rtl { direction: rtl; text-align: right; }
.meta-chip {
  display: inline-block;
  border: 1px solid #34343A;
  background: #1A1A1D;
  border-radius: 999px;
  padding: 0.2rem 0.7rem;
  margin: 0.15rem 0.3rem 0.5rem 0;
  font-size: 0.8rem;
  color: #C9C9CF;
}
.empty-state { padding: 2.2rem 1rem; text-align: center; color: #8E8E96; }
.status-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-inline-end:6px; }
.status-ok { background:#3DDC84; }
.status-warn { background:#F5A524; }
.status-off { background:#6B6B72; }
div[data-testid="stMetric"] {
  background: #141416;
  border: 1px solid #2A2A2E;
  border-radius: 12px;
  padding: 0.7rem 0.85rem;
}
div[data-testid="stMetricLabel"] { overflow: hidden; }
div[data-testid="stMetricValue"] { line-height: 1.2; }
</style>
"""


def contains_persian(text: Any) -> bool:
    return bool(PERSIAN_RE.search(str(text or "")))


def humanize_column(name: Any) -> str:
    raw = str(name or "").strip()
    if raw in COLUMN_LABELS:
        return COLUMN_LABELS[raw]
    key = raw.lower()
    if key in COLUMN_LABELS:
        return COLUMN_LABELS[key]
    if contains_persian(raw):
        return raw
    return re.sub(r"[_\s]+", " ", raw).strip().title() or raw


def is_persian_context(question: str, df: Optional[pd.DataFrame] = None) -> bool:
    if contains_persian(question):
        return True
    if df is not None and not df.empty:
        sample = " ".join(map(str, list(df.columns)[:6]))
        if contains_persian(sample):
            return True
        head = df.head(8).astype(str).to_numpy().flatten()
        if any(contains_persian(v) for v in head[:40]):
            return True
    return False


def escape(text: Any) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def _numeric_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return pd.Series([pd.NA] * len(series), index=series.index, dtype="float64")
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


def is_numeric_col(series: pd.Series) -> bool:
    converted = _numeric_series(series)
    usable = converted.notna().mean()
    return bool(usable >= 0.8 and converted.notna().sum() >= 1)


def is_percent_col(name: Any, series: Optional[pd.Series] = None) -> bool:
    n = str(name).lower()
    if any(h in n for h in ("pct", "percent", "درصد", "share", "سهم", "growth", "رشد")):
        return True
    if series is None or not is_numeric_col(series):
        return False
    vals = _numeric_series(series).dropna()
    if vals.empty:
        return False
    return bool(vals.between(0, 1).mean() > 0.9 and float(vals.max()) <= 1)


def is_time_col(name: Any, series: pd.Series) -> bool:
    n = str(name).lower()
    if any(h in n for h in TIME_NAME_HINTS):
        return True
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if is_numeric_col(series):
        return False
    sample = series.dropna().astype(str).head(12)
    if sample.empty:
        return False
    looks_dated = sample.str.match(r"^(\d{4}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})").mean()
    if looks_dated < 0.6:
        return False
    parsed = pd.to_datetime(sample, errors="coerce")
    return bool(parsed.notna().mean() >= 0.7)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict, tuple, set, bytes)):
        return False
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def format_number(value: Any, *, compact: bool = False, percent: bool = False) -> str:
    if _is_missing(value):
        return "—"
    if isinstance(value, bool) or isinstance(value, (str, bytes)):
        if percent:
            try:
                value = float(value)
            except (TypeError, ValueError):
                return str(value)
        else:
            return str(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if percent:
        sign = "+" if number > 0 else ""
        if abs(number) >= 100:
            return f"{sign}{number:,.0f}%"
        return f"{sign}{number:,.1f}%"
    abs_n = abs(number)
    if compact:
        if abs_n >= 1_000_000_000:
            return f"{number / 1_000_000_000:.1f}B"
        if abs_n >= 1_000_000:
            return f"{number / 1_000_000:.1f}M"
        if abs_n >= 10_000:
            return f"{number:,.0f}"
        if abs_n >= 100:
            return f"{number:,.0f}"
        return f"{number:,.2f}"
    if number.is_integer() or abs_n >= 100:
        return f"{number:,.0f}"
    return f"{number:,.2f}"


def _looks_like_id(name: Any) -> bool:
    n = str(name).lower()
    return n.endswith("_id") or n in {"id", "index"}


PREFERRED_CATS = (
    "dimension", "brand_name", "city", "category_level1", "category",
    "gender", "customer_name", "order_items_name", "product",
)
PREFERRED_METRICS = (
    "pct_change", "difference", "revenue", "total_revenue", "order_count",
    "quantity", "share", "total_qty",
)


def _pick_category(non_numeric, time_cols, work: pd.DataFrame):
    candidates = [c for c in non_numeric if c not in time_cols]
    if not candidates:
        return None
    lowered = {str(c).lower(): c for c in candidates}
    for name in PREFERRED_CATS:
        if name in lowered:
            return lowered[name]
        for c in candidates:
            if name in str(c).lower():
                return c
    return sorted(candidates, key=lambda c: work[c].nunique(), reverse=True)[0]


def _pick_metric(numeric, exclude) -> Optional[Any]:
    pool = [c for c in numeric if c not in exclude]
    if not pool:
        return None
    lowered = {str(c).lower(): c for c in pool}
    for name in PREFERRED_METRICS:
        if name in lowered:
            return lowered[name]
    return pool[0]


def _too_many_dimensions(work: pd.DataFrame, non_numeric, time_cols) -> bool:
    cats = [c for c in non_numeric if c not in time_cols]
    high = [c for c in cats if work[c].nunique() >= 8]
    return len(high) >= 2 and len(work) > 25


def infer_presentation(
    df: Optional[pd.DataFrame],
    question: str = "",
    agent_chart: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Choose KPI / chart / table from the dataframe. Never invent data."""
    q = (question or "").lower()
    empty = {
        "show_kpi": False, "kpis": [], "chart": None, "show_table": False,
        "reason": "no_data",
    }
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return empty

    work = df.copy()
    cols = list(work.columns)
    n_rows, n_cols = len(work), len(cols)
    numeric = [c for c in cols if is_numeric_col(work[c]) and not _looks_like_id(c)]
    non_numeric = [c for c in cols if c not in numeric]
    time_cols = [c for c in cols if is_time_col(c, work[c])]
    rank_q = any(h in q for h in RANK_QUESTION_HINTS)
    share_q = any(h in q for h in SHARE_QUESTION_HINTS)
    time_q = any(h in q for h in TIME_QUESTION_HINTS)

    kpis: List[Dict[str, str]] = []
    show_kpi = False
    if n_rows == 1 and 1 <= len(numeric) <= 6 and n_cols <= 6:
        show_kpi = True
        row = work.iloc[0]
        for col in cols:
            if col in numeric:
                percent = is_percent_col(col, work[col])
                kpis.append({
                    "label": humanize_column(col),
                    "value": format_number(row[col], compact=not percent, percent=percent),
                })
            elif n_cols <= 2:
                kpis.append({"label": humanize_column(col), "value": str(row[col])})

    show_table = n_rows > 1 or (not show_kpi)
    if show_kpi and n_rows == 1:
        show_table = False

    chart = None
    if n_rows >= 2 and numeric:
        x_time = time_cols[0] if time_cols else None
        y_num = None
        if x_time:
            y_candidates = [c for c in numeric if c != x_time]
            y_num = y_candidates[0] if y_candidates else None
        cat = _pick_category(non_numeric, time_cols, work)
        y_metric = _pick_metric(numeric, {x_time, cat})

        # Time series
        if x_time and y_num and work[x_time].nunique() >= 2:
            chart = {
                "type": "line",
                "x": x_time,
                "y": y_num,
                "title": humanize_column(y_num),
                "orientation": "v",
            }
        # Two numeric relationship
        elif (
            len(numeric) >= 2
            and n_rows >= 8
            and not time_cols
            and not rank_q
            and n_cols <= 4
            and len(non_numeric) == 0
        ):
            chart = {
                "type": "scatter",
                "x": numeric[0],
                "y": numeric[1],
                "title": f"{humanize_column(numeric[1])} vs {humanize_column(numeric[0])}",
                "orientation": "v",
            }
        # Category + metric (bar/pie). Truncate long rankings in the chart renderer.
        elif cat and y_metric and not _too_many_dimensions(work, non_numeric, time_cols):
            vals = _numeric_series(work[y_metric]).dropna()
            share_metric = is_percent_col(y_metric, work[y_metric])
            unique_cats = work[cat].nunique()
            pie_ok = (
                2 <= unique_cats <= 8
                and n_rows <= 8
                and (share_q or share_metric)
                and not time_cols
                and bool((vals >= 0).all())
                and float(vals.sum()) > 0
            )
            if unique_cats < 2:
                chart = None
            elif pie_ok:
                chart = {
                    "type": "pie",
                    "x": cat,
                    "y": y_metric,
                    "names": cat,
                    "values": y_metric,
                    "title": humanize_column(y_metric),
                    "orientation": "v",
                }
            else:
                horizontal = rank_q or unique_cats > 8 or n_rows > 8
                chart = {
                    "type": "bar",
                    "x": y_metric if horizontal else cat,
                    "y": cat if horizontal else y_metric,
                    "orientation": "h" if horizontal else "v",
                    "category": cat,
                    "metric": y_metric,
                    "title": humanize_column(y_metric),
                }

    # Prefer inferred chart over agent histogram; otherwise fill gaps from agent spec
    if chart is None and agent_chart and isinstance(agent_chart, dict):
        kind = agent_chart.get("type")
        if kind in {"bar", "line"} and agent_chart.get("x") in cols and (
            agent_chart.get("y") in cols or kind == "line"
        ):
            chart = {
                "type": kind,
                "x": agent_chart.get("x"),
                "y": agent_chart.get("y"),
                "orientation": agent_chart.get("orientation", "v"),
                "title": agent_chart.get("title") or humanize_column(agent_chart.get("y") or agent_chart.get("x")),
            }

    return {
        "show_kpi": show_kpi,
        "kpis": kpis,
        "chart": chart,
        "show_table": show_table,
        "reason": "ok",
        "rtl": is_persian_context(question, work),
    }


def _plotly_layout(fig: go.Figure, title: str, rtl: bool = False) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0.0, xanchor="left", font=dict(size=15, color="#E8E8EC"), pad=dict(t=4, b=8)),
        margin=dict(l=56, r=28, t=64, b=56),
        font=dict(family="IBM Plex Sans, Vazirmatn, sans-serif", size=13, color="#D0D0D6"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.08, x=0, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(
            showgrid=True, gridcolor="rgba(255,255,255,0.08)", zeroline=False,
            tickfont=dict(color="#B5B5BC"), title_font=dict(color="#C9C9CF"),
        ),
        yaxis=dict(
            showgrid=True, gridcolor="rgba(255,255,255,0.08)", zeroline=False,
            tickfont=dict(color="#B5B5BC"), title_font=dict(color="#C9C9CF"),
        ),
    )
    if rtl:
        fig.update_layout(title=dict(x=1.0, xanchor="right"))
    return fig


def build_chart(df: pd.DataFrame, spec: Dict[str, Any], rtl: bool = False) -> Optional[go.Figure]:
    if not spec or df is None or df.empty:
        return None
    kind = spec.get("type")
    work = df.copy()
    title = spec.get("title") or ""

    def label(col: Any) -> str:
        return humanize_column(col)

    try:
        if kind == "line":
            x, y = spec["x"], spec["y"]
            if x not in work.columns or y not in work.columns:
                return None
            if is_time_col(x, work[x]) and not pd.api.types.is_datetime64_any_dtype(work[x]):
                parsed = pd.to_datetime(work[x], errors="coerce")
                if parsed.notna().mean() >= 0.5:
                    work[x] = parsed
            work[y] = _numeric_series(work[y])
            work = work.dropna(subset=[y])
            if work.empty or work[x].nunique() < 2:
                return None
            fig = px.line(work, x=x, y=y, markers=True)
            fig.update_traces(
                hovertemplate=f"{label(x)}: %{{x}}<br>{label(y)}: %{{y:,.2f}}<extra></extra>",
                line=dict(width=2.4, color="#5B9DFF"),
                marker=dict(size=7, color="#8CBCFF"),
            )
            fig.update_layout(xaxis_title=label(x), yaxis_title=label(y))
            return _plotly_layout(fig, title, rtl)

        if kind == "bar":
            orientation = spec.get("orientation", "v")
            cat = spec.get("category")
            metric = spec.get("metric")
            if cat and metric and cat in work.columns and metric in work.columns:
                x, y = (metric, cat) if orientation == "h" else (cat, metric)
            else:
                x, y = spec.get("x"), spec.get("y")
            if x not in work.columns or y not in work.columns:
                return None
            value_col = x if orientation == "h" else y
            cat_col = y if orientation == "h" else x
            work[value_col] = _numeric_series(work[value_col])
            work = work.dropna(subset=[value_col])
            if work.empty or work[cat_col].nunique() < 2:
                return None
            work = work.sort_values(value_col, ascending=orientation == "h").head(25)
            fig = px.bar(work, x=x, y=y, orientation=orientation)
            fig.update_traces(hovertemplate="%{x}<br>%{y}<extra></extra>", marker_color="#5B9DFF")
            fig.update_layout(xaxis_title=label(x), yaxis_title=label(y))
            if orientation == "h":
                fig.update_layout(yaxis=dict(categoryorder="total ascending"))
            return _plotly_layout(fig, title, rtl)

        if kind == "pie":
            names, values = spec.get("names") or spec.get("x"), spec.get("values") or spec.get("y")
            if names not in work.columns or values not in work.columns:
                return None
            work[values] = _numeric_series(work[values])
            work = work.dropna(subset=[values])
            work = work[work[values] > 0]
            if not (2 <= len(work) <= 8):
                return None
            fig = px.pie(work, names=names, values=values, hole=0.35)
            fig.update_traces(
                textposition="inside",
                textinfo="percent+label",
                hovertemplate="%{label}: %{value:,.2f} (%{percent})<extra></extra>",
            )
            fig.update_layout(showlegend=True)
            return _plotly_layout(fig, title, rtl)

        if kind == "scatter":
            x, y = spec["x"], spec["y"]
            if x not in work.columns or y not in work.columns:
                return None
            work[x] = _numeric_series(work[x])
            work[y] = _numeric_series(work[y])
            work = work.dropna(subset=[x, y])
            if len(work) < 8:
                return None
            fig = px.scatter(work, x=x, y=y)
            fig.update_traces(
                hovertemplate=f"{label(x)}: %{{x:,.2f}}<br>{label(y)}: %{{y:,.2f}}<extra></extra>",
                marker=dict(size=9, color="#5B9DFF", opacity=0.85),
            )
            fig.update_layout(xaxis_title=label(x), yaxis_title=label(y))
            return _plotly_layout(fig, title, rtl)
    except Exception:
        return None
    return None


def prepare_display_frame(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    display = df.copy()
    display.columns = [humanize_column(c) for c in display.columns]
    config: Dict[str, Any] = {}
    try:
        from streamlit import column_config
    except Exception:
        column_config = None  # type: ignore

    for orig, new in zip(df.columns, display.columns):
        series = df[orig]
        if pd.api.types.is_datetime64_any_dtype(series):
            if is_time_col(orig, series) and "month" in str(orig).lower():
                display[new] = pd.to_datetime(series).dt.strftime("%Y-%m")
            else:
                display[new] = pd.to_datetime(series).dt.strftime("%Y-%m-%d")
            if column_config is not None:
                config[new] = column_config.TextColumn(new, width="small")
            continue
        if series.dtype == object:
            parsed = pd.to_datetime(series, errors="coerce")
            if parsed.notna().mean() >= 0.8:
                display[new] = parsed.dt.strftime("%Y-%m-%d")
                if column_config is not None:
                    config[new] = column_config.TextColumn(new, width="small")
                continue
            display[new] = series.map(_stringify_cell)
        if column_config is None:
            continue
        if is_percent_col(orig, series):
            config[new] = column_config.NumberColumn(new, format="%.1f%%")
        elif is_numeric_col(series):
            sample = _numeric_series(series).dropna()
            fmt = "%.0f" if not sample.empty and (sample.abs() >= 100).mean() > 0.6 else "%.2f"
            config[new] = column_config.NumberColumn(new, format=fmt)
        else:
            config[new] = column_config.TextColumn(new, width="medium")
    return display, config


def _stringify_cell(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return str(value)
    return value


def firewall_status(events: List[Dict], result: Dict) -> str:
    if result.get("route_taken") == "blocked":
        return "Blocked"
    if any(e.get("type") == "firewall_block" for e in events):
        return "Blocked"
    if result.get("sql"):
        return "Passed"
    return "Not run"


def reflection_status(events: List[Dict], result: Dict) -> str:
    retries = int(result.get("retry") or 0)
    n = sum(1 for e in events if e.get("type") == "reflection")
    if n or retries:
        return f"Retried ({max(n, retries)})"
    return "Not needed"


def analysis_type_label(plan: Optional[Dict]) -> str:
    if not plan:
        return ""
    raw = str(plan.get("analysis_type") or "")
    return ANALYSIS_TYPE_LABELS.get(raw, raw.replace("_", " ").title())


def safe_step_summaries(steps: Optional[List]) -> List[Dict[str, Any]]:
    out = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        out.append({
            "id": step.get("id"),
            "kind": step.get("kind") or step.get("operation"),
            "ok": bool(step.get("ok")),
            "value": step.get("value"),
        })
    return out
