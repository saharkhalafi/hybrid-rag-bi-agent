"""Execute a validated analytical plan through the existing SQL pipeline.

Known metric/period/dimension steps use deterministic SQL (still firewall + exec_node).
Arithmetic / ranking stay in Python. Gemini SQL generation is only a fallback.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.agent.routing import _norm
from src.db.schema import JALALI_TO_GREGORIAN
from src.observability.telemetry import get_events, log_event
from src.security.firewall import sql_firewall

METRIC_FA = {
    "revenue": "فروش",
    "orders": "تعداد سفارش",
    "quantity": "تعداد کالا",
    "aov": "میانگین ارزش سفارش",
    "discount": "تخفیف",
}
DIM_FA = {
    "city": "شهر",
    "brand": "برند",
    "category": "دسته",
    "product": "محصول",
    "gender": "جنسیت",
}
DIM_COL = {
    "city": "city",
    "brand": "brand_name",
    "category": "category_level1",
    "product": "order_items_name",
    "gender": "gender",
}
METRIC_EXPR = {
    "revenue": 'SUM("revenue")',
    "orders": 'COUNT(DISTINCT "order_id")',
    "quantity": 'SUM("quantity")',
    "discount": 'SUM("discount_amount")',
    "aov": 'SUM("revenue") / NULLIF(COUNT(DISTINCT "order_id"), 0)',
}
PYTHON_OPS = {"percentage_change", "difference", "ratio", "rank", "sort"}
EN_MONTH_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def fetch_question(step: dict) -> str:
    if step.get("question"):
        return step["question"]
    metric = METRIC_FA.get(step.get("metric") or "revenue", "فروش")
    period = step.get("period")
    dim = step.get("dimension")
    if dim:
        q = f"{metric} هر {DIM_FA.get(dim, dim)}"
    elif (step.get("metric") or "revenue") == "orders":
        q = "تعداد سفارش‌ها چقدر بوده"
    else:
        q = f"{metric} چقدر بوده"
    if period:
        q += f" در ماه {period}"
    return q


def month_number(period: Optional[str]) -> Optional[int]:
    if not period:
        return None
    p = _norm(period)
    for fa, en in JALALI_TO_GREGORIAN.items():
        if _norm(fa) == p:
            return EN_MONTH_NUM.get(en.lower())
    return EN_MONTH_NUM.get(p)


def _month_pred(month: int) -> str:
    return f'EXTRACT(MONTH FROM "order_date") = {int(month)}'


def _metric_expr(metric: str) -> Optional[str]:
    return METRIC_EXPR.get(metric or "revenue")


def _first_numeric(df: Optional[pd.DataFrame]) -> Optional[float]:
    if df is None or df.empty:
        return None
    for col in df.columns:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if not series.empty:
            return float(series.iloc[0])
    return None


def _numeric_column(df: pd.DataFrame) -> Optional[str]:
    for col in reversed(list(df.columns)):
        if pd.to_numeric(df[col], errors="coerce").notna().any():
            return col
    return None


def _label_column(df: pd.DataFrame) -> Optional[str]:
    num = _numeric_column(df)
    for col in df.columns:
        if col != num:
            return col
    return None


def percentage_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous * 100.0


def difference(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None:
        return None
    return current - previous


def ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _scalar_of(result: dict) -> Optional[float]:
    if result.get("value") is not None:
        try:
            return float(result["value"])
        except (TypeError, ValueError):
            return None
    return _first_numeric(result.get("dataframe"))


def build_scalar_sql(metric: str, period: Optional[str] = None) -> Optional[str]:
    expr = _metric_expr(metric)
    month = month_number(period) if period else None
    if expr is None or (period and month is None):
        return None
    sql = f'SELECT {expr} AS value FROM "orders"'
    if month:
        sql += f" WHERE {_month_pred(month)}"
    return sql


def build_two_period_sql(metric: str, current_period: str, previous_period: str) -> Optional[str]:
    expr = _metric_expr(metric)
    cur, prev = month_number(current_period), month_number(previous_period)
    if expr is None or cur is None or prev is None or cur == prev:
        return None
    return (
        f'SELECT EXTRACT(MONTH FROM "order_date")::int AS month_num, {expr} AS value '
        f'FROM "orders" WHERE EXTRACT(MONTH FROM "order_date") IN ({cur}, {prev}) '
        f"GROUP BY 1"
    )


def build_breakdown_sql(metric: str, dim: str, current_period: str, previous_period: str) -> Optional[str]:
    expr = _metric_expr(metric)
    col = DIM_COL.get(dim)
    cur, prev = month_number(current_period), month_number(previous_period)
    if expr is None or col is None or cur is None or prev is None or cur == prev:
        return None
    if metric == "orders":
        cur_expr = f'COUNT(DISTINCT CASE WHEN {_month_pred(cur)} THEN "order_id" END)'
        prev_expr = f'COUNT(DISTINCT CASE WHEN {_month_pred(prev)} THEN "order_id" END)'
    elif metric == "aov":
        cur_expr = (
            f'SUM(CASE WHEN {_month_pred(cur)} THEN "revenue" ELSE 0 END) / '
            f'NULLIF(COUNT(DISTINCT CASE WHEN {_month_pred(cur)} THEN "order_id" END), 0)'
        )
        prev_expr = (
            f'SUM(CASE WHEN {_month_pred(prev)} THEN "revenue" ELSE 0 END) / '
            f'NULLIF(COUNT(DISTINCT CASE WHEN {_month_pred(prev)} THEN "order_id" END), 0)'
        )
    else:
        col_src = {"revenue": "revenue", "quantity": "quantity", "discount": "discount_amount"}[metric]
        cur_expr = f'SUM(CASE WHEN {_month_pred(cur)} THEN "{col_src}" ELSE 0 END)'
        prev_expr = f'SUM(CASE WHEN {_month_pred(prev)} THEN "{col_src}" ELSE 0 END)'
    return (
        f'SELECT "{col}" AS dimension, {cur_expr} AS current, {prev_expr} AS previous '
        f'FROM "orders" WHERE EXTRACT(MONTH FROM "order_date") IN ({cur}, {prev}) '
        f'GROUP BY "{col}"'
    )


def _run_approved_sql(sql: str) -> dict:
    from src.agent.graph import exec_node

    fw = sql_firewall(sql)
    if not fw.ok:
        return {"ok": False, "error": fw.message, "sql": sql, "deterministic": True, "dataframe": None, "value": None}
    started = time.time()
    state = exec_node({"sql": fw.sql, "retry": 0, "error": None, "messages": []})
    db_ms = round((time.time() - started) * 1000, 2)
    df = state.get("dataframe")
    ok = not state.get("error") and df is not None
    return {
        "ok": bool(ok), "error": state.get("error"), "sql": state.get("sql") or fw.sql,
        "dataframe": df, "value": _first_numeric(df) if ok else None,
        "deterministic": True, "db_ms": db_ms,
    }


def _run_fetch(question: str) -> dict:
    from src.agent.graph import exec_node, sql_node

    state = sql_node({"question": question, "retry": 0, "error": None, "messages": []})
    if not state.get("sql"):
        return {"ok": False, "error": state.get("error") or "No SQL generated", "state": state,
                "sql": None, "dataframe": None, "value": None, "deterministic": False}
    state = exec_node(state)
    df = state.get("dataframe")
    ok = not state.get("error") and df is not None
    return {"ok": bool(ok), "error": state.get("error"), "state": state, "dataframe": df,
            "sql": state.get("sql"), "value": _first_numeric(df) if ok else None, "deterministic": False}


def _fetch_step(step: dict) -> dict:
    metric = step.get("metric") or "revenue"
    sql = build_scalar_sql(metric, step.get("period"))
    if sql:
        out = _run_approved_sql(sql)
        if out["ok"]:
            return out
    return _run_fetch(fetch_question(step))


def _align_from_two_col(df: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    if df is None or df.empty or "current" not in df.columns or "previous" not in df.columns:
        return pd.DataFrame()
    table = df.copy()
    if "dimension" not in table.columns:
        label = _label_column(table)
        if label:
            table = table.rename(columns={label: "dimension"})
    table["current"] = pd.to_numeric(table["current"], errors="coerce").fillna(0)
    table["previous"] = pd.to_numeric(table["previous"], errors="coerce").fillna(0)
    table["difference"] = table["current"] - table["previous"]
    table["pct_change"] = table.apply(
        lambda r: percentage_change(r["current"], r["previous"]) if r["previous"] else None, axis=1
    )
    return table.sort_values("difference", ascending=True).head(top_n).reset_index(drop=True)


def _split_two_period(df: pd.DataFrame, current_month: int, previous_month: int) -> Tuple[Optional[float], Optional[float]]:
    if df is None or df.empty:
        return None, None
    month_col = "month_num" if "month_num" in df.columns else df.columns[0]
    val_col = "value" if "value" in df.columns else df.columns[-1]
    by_month = {}
    for _, row in df.iterrows():
        try:
            by_month[int(row[month_col])] = float(row[val_col])
        except (TypeError, ValueError):
            continue
    return by_month.get(current_month, 0.0), by_month.get(previous_month, 0.0)


def _periods_from_plan(steps: List[dict]) -> Tuple[str, str]:
    labeled = [s.get("period") for s in steps if s.get("period")]
    current = labeled[0] if labeled else "شهریور"
    previous = labeled[1] if len(labeled) >= 2 else ("مرداد" if current != "مرداد" else "شهریور")
    return current, previous


def _align_breakdown(current_df: pd.DataFrame, previous_df: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    left_key, right_key = _label_column(current_df), _label_column(previous_df)
    left_val, right_val = _numeric_column(current_df), _numeric_column(previous_df)
    if not all([left_key, right_key, left_val, right_val]):
        return pd.DataFrame()
    cur = current_df[[left_key, left_val]].copy()
    prev = previous_df[[right_key, right_val]].copy()
    cur.columns = ["dimension", "current"]
    prev.columns = ["dimension", "previous"]
    cur["current"] = pd.to_numeric(cur["current"], errors="coerce")
    prev["previous"] = pd.to_numeric(prev["previous"], errors="coerce")
    return _align_from_two_col(cur.merge(prev, on="dimension", how="outer").fillna(0), top_n)


def execute_plan(plan: dict, original_question: str) -> dict:
    steps: List[dict] = plan["steps"]
    results: Dict[str, dict] = {}
    sql_parts: List[str] = []
    fetch_ok = fetch_total = calc_ok = deterministic_steps = db_queries = 0
    display_df = pd.DataFrame()
    events_before = len(get_events())

    fetch_steps = [s for s in steps if (s.get("operation") or "fetch") == "fetch" and not s.get("dimension")]
    by_metric: Dict[str, List[dict]] = {}
    for s in fetch_steps:
        by_metric.setdefault(s.get("metric") or "revenue", []).append(s)

    for metric, group in by_metric.items():
        if len(group) != 2 or not all(g.get("period") for g in group):
            continue
        sql = build_two_period_sql(metric, group[0]["period"], group[1]["period"])
        if not sql:
            continue
        fetch_total += 2
        out = _run_approved_sql(sql)
        db_queries += 1
        if out.get("sql"):
            sql_parts.append(out["sql"])
        if not out["ok"]:
            fetch_total -= 2
            db_queries -= 1
            continue
        deterministic_steps += 1
        cur_m, prev_m = month_number(group[0]["period"]), month_number(group[1]["period"])
        v0, v1 = _split_two_period(out["dataframe"], cur_m, prev_m)
        for step, value in ((group[0], v0), (group[1], v1)):
            ok = value is not None
            if ok:
                fetch_ok += 1
            results[step["id"]] = {
                "id": step["id"], "kind": "sql", "ok": ok, "error": None if ok else "missing period row",
                "sql": out.get("sql"), "value": value, "question": fetch_question(step), "deterministic": True,
            }
            log_event({"type": "analysis_step", "id": step["id"], "kind": "sql", "success": ok, "deterministic": True})

    for step in steps:
        sid = step["id"]
        if sid in results:
            continue
        op = step.get("operation") or "fetch"
        try:
            if op in PYTHON_OPS:
                inputs = step.get("inputs") or []
                values = [_scalar_of(results[i]) for i in inputs if i in results]
                value = None
                if op == "percentage_change" and len(values) >= 2:
                    value = percentage_change(values[0], values[1])
                elif op == "difference" and len(values) >= 2:
                    value = difference(values[0], values[1])
                elif op == "ratio" and len(values) >= 2:
                    value = ratio(values[0], values[1])
                elif op in {"rank", "sort"} and inputs:
                    src = results.get(inputs[0], {})
                    df = src.get("dataframe")
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        col = _numeric_column(df)
                        display_df = df.sort_values(col, ascending=True).head(step.get("top_n") or 10) if col else df
                        value = _first_numeric(display_df)
                ok = value is not None or (op in {"rank", "sort"} and not display_df.empty)
                if ok:
                    calc_ok += 1
                    deterministic_steps += 1
                results[sid] = {"id": sid, "kind": "python", "ok": ok,
                                "error": None if ok else "calculation failed", "value": value, "sql": None}
                log_event({"type": "analysis_step", "id": sid, "kind": "python", "success": ok, "operation": op})
                continue

            if op == "dimension_breakdown":
                dims = step.get("dimensions") or ([step["dimension"]] if step.get("dimension") else ["city"])
                metric = step.get("metric") or "revenue"
                current_p, previous_p = _periods_from_plan(steps)
                frames = []
                ok_any = False
                for dim in dims[:3]:
                    sql = build_breakdown_sql(metric, dim, current_p, previous_p)
                    if sql:
                        fetch_total += 1
                        out = _run_approved_sql(sql)
                        db_queries += 1
                        if out.get("sql"):
                            sql_parts.append(out["sql"])
                        if out["ok"]:
                            deterministic_steps += 1
                            table = _align_from_two_col(out["dataframe"], step.get("top_n") or 8)
                            if not table.empty:
                                table.insert(0, "breakdown", dim)
                                frames.append(table)
                                ok_any = True
                                fetch_ok += 1
                                calc_ok += 1
                        log_event({"type": "analysis_step", "id": f"{sid}_{dim}", "kind": "dimension_breakdown",
                                   "success": bool(out.get("ok")), "deterministic": True})
                    else:
                        fetch_total += 2
                        cur = _run_fetch(fetch_question({"metric": metric, "period": current_p, "dimension": dim}))
                        prev = _run_fetch(fetch_question({"metric": metric, "period": previous_p, "dimension": dim}))
                        db_queries += 2
                        if cur.get("ok") and prev.get("ok"):
                            table = _align_breakdown(cur["dataframe"], prev["dataframe"], step.get("top_n") or 8)
                            table.insert(0, "breakdown", dim)
                            frames.append(table)
                            ok_any = True
                            fetch_ok += 2
                            calc_ok += 1
                combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
                results[sid] = {"id": sid, "kind": "dimension_breakdown", "ok": ok_any and not combined.empty,
                                "error": None if not combined.empty else "breakdown failed",
                                "dataframe": combined, "value": None}
                if not combined.empty:
                    display_df = combined
                continue

            fetch_total += 1
            out = _fetch_step(step)
            db_queries += 1
            results[sid] = {"id": sid, "kind": "sql", "ok": out.get("ok"), "error": out.get("error"),
                            "sql": out.get("sql"), "value": out.get("value"), "question": fetch_question(step),
                            "deterministic": bool(out.get("deterministic"))}
            if out.get("sql"):
                sql_parts.append(out["sql"])
            if out.get("ok"):
                fetch_ok += 1
                if out.get("deterministic"):
                    deterministic_steps += 1
                df = out.get("dataframe")
                if df is not None and not df.empty and (df.shape[1] >= 2 or display_df.empty):
                    display_df = df
            log_event({"type": "analysis_step", "id": sid, "kind": "sql", "success": out.get("ok"),
                       "deterministic": bool(out.get("deterministic"))})
        except Exception as exc:
            results[sid] = {"id": sid, "kind": op, "ok": False, "error": str(exc)[:200], "value": None}
            log_event({"type": "analysis_step", "id": sid, "kind": op, "success": False, "error": str(exc)[:200]})

    summary_rows = [{"step": sid, "value": res["value"]} for sid, res in results.items() if res.get("value") is not None]
    summary_df = pd.DataFrame(summary_rows)
    if display_df is None or display_df.empty:
        display_df = summary_df

    explanation = _explain(original_question, results, display_df)
    sql_blob = "\n\n".join(sql_parts) if sql_parts else None
    step_ok = sum(1 for r in results.values() if r.get("ok"))
    new_events = get_events()[events_before:]
    llm = [e for e in new_events if e.get("type") == "llm_call"]
    telemetry = {
        "sql_llm_calls": sum(1 for e in llm if e.get("node") in {"sql", "sql_reflect"}),
        "final_llm_calls": sum(1 for e in llm if e.get("node") in {"explain", "synthesis"}),
        "deterministic_steps": deterministic_steps,
        "db_queries": db_queries,
        "llm_latency_ms": round(sum(float(e.get("latency_ms") or 0) for e in llm), 2),
        "db_latency_ms": round(sum(float(e.get("sql_execution_ms") or 0) for e in new_events
                                   if e.get("type") == "sql_executed"), 2),
        "estimated_cost": round(sum(float(e.get("estimated_cost") or 0) for e in llm), 6),
    }
    log_event({"type": "analysis_complete", "steps_ok": step_ok, "steps_total": len(results),
               "fetch_ok": fetch_ok, "fetch_total": fetch_total, **telemetry})
    error = None if step_ok else "All analytical steps failed"
    return {
        "dataframe": display_df if display_df is not None else pd.DataFrame(),
        "summary": summary_df,
        "explanation": explanation,
        "sql": sql_blob,
        "error": error,
        "step_results": list(results.values()),
        "fetch_ok": fetch_ok,
        "fetch_total": fetch_total,
        "calc_ok": calc_ok,
        "steps_ok": step_ok,
        "steps_total": len(results),
        "telemetry": telemetry,
    }


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "نامشخص"
    if abs(v) >= 100:
        return f"{v:,.0f}"
    return f"{v:,.2f}"


def _explain(question: str, results: Dict[str, dict], display_df: pd.DataFrame) -> str:
    parts = []
    for sid, res in results.items():
        if res.get("kind") == "python" and res.get("value") is not None:
            if "change" in sid or "pct" in sid:
                parts.append(f"تغییر {sid}: {_fmt(res['value'])}٪")
            else:
                parts.append(f"{sid}: {_fmt(res['value'])}")
        elif res.get("kind") == "sql" and res.get("value") is not None:
            parts.append(f"{sid}: {_fmt(res['value'])}")
    if isinstance(display_df, pd.DataFrame) and not display_df.empty and "difference" in display_df.columns:
        top = display_df.iloc[0]
        dim = top.get("dimension", "")
        parts.append(f"بیشترین افت در {dim} ({_fmt(top.get('pct_change'))}٪).")
    return " ".join(parts).strip() or "تحلیل چندمرحله‌ای اجرا شد."
