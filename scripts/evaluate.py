"""Execution-accuracy evaluation of the BI agent against a versioned gold set.

For every gold question the full agent runs (template retrieval -> compatibility guard
-> Gemini fallback -> firewall -> Postgres -> reflection). The *result set* of the
agent's SQL is compared with the result set of the gold SQL, Spider-style:

  strict   : same multiset of rows (column names/order ignored, numbers compared with
             0.1% relative tolerance, dates normalised)
  lenient  : every gold column is matched by some predicted column (extra columns OK)

The report separates retrieval, routing, execution, result correctness, reflection,
LLM usage, template usage, latency and cost, adds an error breakdown, and (by default)
compares two routing modes on the same gold set:

  baseline : similarity >= RAG_SIMILARITY_THRESHOLD is sufficient to use a template
  improved : similarity + deterministic compatibility checks (filters/time/top-N/dims/metrics)

Usage:
  python scripts/evaluate.py                                   # v2 gold set, both modes
  python scripts/evaluate.py --gold evaluation/gold_set.json   # original v1 benchmark
  python scripts/evaluate.py --modes improved                  # single mode
  python scripts/evaluate.py --out evaluation/reports/run.json
"""
import argparse
import json
import math
import sys
import time
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.complexity import detect_complexity  # noqa: E402
from src.agent.graph import run_question  # noqa: E402
from src.agent.routing import detect_intent, set_routing_mode  # noqa: E402
from src.config import RAG_SIMILARITY_THRESHOLD, clear_caches  # noqa: E402
from src.db.engine import get_engine  # noqa: E402
from src.observability.telemetry import get_events, reset_events  # noqa: E402
from src.rag.retriever import is_available  # noqa: E402

GOLD_PATH = PROJECT_ROOT / "evaluation" / "gold_set_v2.json"
ANALYTICAL_PATH = PROJECT_ROOT / "evaluation" / "analytical_examples.json"
REPORT_DIR = PROJECT_ROOT / "evaluation" / "reports"
REL_TOL = 1e-3
ERROR_CATEGORIES = ["wrong_template_routing", "sql_generation_error", "schema_error", "temporal_error",
                    "ambiguous_query", "execution_error", "gold_sql_error"]


# ------------------------------------------------------------------ normalisation
def _norm_value(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(v).strftime("%Y-%m-%d")
    if isinstance(v, Decimal):
        v = float(v)
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return round(float(v), 6)
    s = str(v).strip()
    try:
        return round(float(s), 6)
    except ValueError:
        return s.lower()


def _values_equal(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=1.0)
    return a == b


def _rows(df: pd.DataFrame) -> list[tuple]:
    return [tuple(_norm_value(v) for v in row) for row in df.itertuples(index=False, name=None)]


def _multiset_match(pred_rows: list[tuple], gold_rows: list[tuple]) -> bool:
    if len(pred_rows) != len(gold_rows):
        return False
    remaining = list(gold_rows)
    for pr in pred_rows:
        hit = next((i for i, gr in enumerate(remaining)
                    if len(gr) == len(pr) and all(_values_equal(x, y) for x, y in zip(pr, gr))), None)
        if hit is None:
            return False
        remaining.pop(hit)
    return True


def strict_match(pred: pd.DataFrame, gold: pd.DataFrame) -> bool:
    if pred.shape != gold.shape:
        return False
    # try direct column order, then permutation-free multiset with sorted columns
    if _multiset_match(_rows(pred), _rows(gold)):
        return True
    pred_sorted = pred[sorted(pred.columns, key=lambda c: str(pred[c].dtype))]
    gold_sorted = gold[sorted(gold.columns, key=lambda c: str(gold[c].dtype))]
    return _multiset_match(_rows(pred_sorted), _rows(gold_sorted))


def lenient_match(pred: pd.DataFrame, gold: pd.DataFrame) -> bool:
    if len(pred) != len(gold) or pred.empty:
        return False
    pred_cols = {c: sorted((_norm_value(v) for v in pred[c]), key=lambda x: (x is None, str(x))) for c in pred.columns}
    for gc in gold.columns:
        gvals = sorted((_norm_value(v) for v in gold[gc]), key=lambda x: (x is None, str(x)))
        if not any(all(_values_equal(a, b) for a, b in zip(pv, gvals)) for pv in pred_cols.values()):
            return False
    return True


def run_gold_sql(sql: str) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql_query(text(sql), conn)


# ------------------------------------------------------------------ gold set loading
def load_gold(path: Path) -> tuple[list[dict], str]:
    """Accepts v1 (plain list) and v2 ({"version", "items": [...]}) formats."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        items, version = data["items"], data.get("version", path.stem)
    else:
        items, version = data, "v1"
    for item in items:
        item.setdefault("expected_template", None)
        item.setdefault("tags", [])
    return items, version


# ------------------------------------------------------------------ per-question run
def _pct(num, den, digits=1):
    return round(100 * num / den, digits) if den else None


def _avg(values, digits=0):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), digits) if values else None


def _percentile(values, q):
    values = sorted(values)
    return values[max(0, int(q * len(values)) - 1)] if values else None


def classify_error(row: dict) -> str | None:
    """One coarse error category for a row whose result is not (even leniently) correct."""
    if row["lenient_match"]:
        return None
    if row["gold_error"]:
        return "gold_sql_error"
    err = (row["error"] or "").lower()
    if not row["pred_sql"] or row["route"] == "blocked":
        return "sql_generation_error"
    if err:
        if any(k in err for k in ("does not exist", "unknown column", "unauthorized table", "undefined", "column")):
            return "schema_error"
        return "execution_error"
    # SQL executed fine but returned the wrong result set
    if row["route"] == "retriever" and (row["expected_route"] != "retriever" or not row["template_ok"]):
        return "wrong_template_routing"
    if "ambiguous" in row["tags"]:
        return "ambiguous_query"
    if row["signals"].get("dates"):  # question names a month/year/relative period and the window was wrong
        return "temporal_error"
    return "sql_generation_error"  # valid SQL, wrong semantics (e.g. different grouping/representation)


def run_one(item: dict) -> dict:
    clear_caches()  # every question is judged cold (no cross-question cache hits)
    before = len(get_events())
    started = time.time()
    result = run_question(item["question"])
    latency_ms = round((time.time() - started) * 1000)
    events = get_events()[before:]

    pred_df = result.get("dataframe")
    pred_df = pred_df if isinstance(pred_df, pd.DataFrame) else pd.DataFrame()
    try:
        gold_df, gold_error = run_gold_sql(item["sql"]), None
    except Exception as exc:
        gold_df, gold_error = pd.DataFrame(), str(exc)[:200]

    error = result.get("error")
    executed = bool(result.get("sql")) and not error
    strict = bool(executed and gold_error is None and strict_match(pred_df, gold_df))
    lenient = strict or bool(executed and gold_error is None and lenient_match(pred_df, gold_df))

    route = result.get("route_taken")
    template_id = result.get("template_id") if route == "retriever" else None
    candidates = result.get("candidates") or []
    candidate_ids = [c.get("template_id") or (c.get("template") or {}).get("id") for c in candidates]
    top1_score = float(candidates[0]["score"]) if candidates else 0.0
    expected_template = item.get("expected_template")

    llm_calls = [e for e in events if e.get("type") == "llm_call"]
    row = {
        "id": item["id"], "question": item["question"], "tags": item.get("tags", []),
        "expected_route": item["expected_route"], "expected_template": expected_template,
        "route": route, "template_id": template_id,
        "route_ok": route == item["expected_route"],
        # v1 items carry no expected_template: any template counts as correct when the route is right
        "template_ok": (template_id == expected_template) if expected_template else True,
        "similarity": round(float(result.get("similarity_score") or 0), 3),
        "top1_similarity": round(top1_score, 3),
        "top1_template": candidate_ids[0] if candidate_ids else None,
        "retrieved_candidates": candidate_ids,
        "retrieval_top1_ok": (candidate_ids[0] == expected_template) if (expected_template and candidate_ids) else None,
        "retrieval_topk_ok": (expected_template in candidate_ids) if expected_template else None,
        "guard_reason": result.get("guard_reason"),
        "signals": detect_intent(item["question"]).to_dict(),
        "reflections": sum(1 for e in events if e.get("type") == "reflection"),
        "llm_sql_calls": sum(1 for e in llm_calls if e.get("node") == "sql"),
        "llm_reflect_calls": sum(1 for e in llm_calls if e.get("node") == "sql_reflect"),
        "llm_explain_calls": sum(1 for e in llm_calls if e.get("node") == "explain"),
        "llm_planner_calls": sum(1 for e in llm_calls if e.get("node") == "planner"),
        "llm_synthesis_calls": sum(1 for e in llm_calls if e.get("node") == "synthesis"),
        "llm_calls": len(llm_calls),
        "is_complex": detect_complexity(item["question"]).is_complex,
        "multi_step": route == "multi_step",
        "planner_success": any(e.get("type") in {"planner_success", "planner_fallback"} for e in events),
        "steps_ok": next((e.get("steps_ok") for e in reversed(events) if e.get("type") == "analysis_complete"), None),
        "steps_total": next((e.get("steps_total") for e in reversed(events) if e.get("type") == "analysis_complete"), None),
        "llm_tokens": sum(int(e.get("total_tokens") or 0) for e in llm_calls),
        "cost_usd": round(sum(float(e.get("estimated_cost") or 0) for e in llm_calls), 6),
        "firewall_blocks": sum(1 for e in events if e.get("type") == "firewall_block"),
        "sql_errors": sum(1 for e in events if e.get("type") in {"sql_error", "sql_timeout"}),
        "pred_sql": result.get("sql"), "gold_sql": item["sql"],
        "pred_rows": int(len(pred_df)), "gold_rows": int(len(gold_df)),
        "executed": executed, "error": error, "gold_error": gold_error,
        "strict_match": strict, "lenient_match": lenient,
        "latency_ms": latency_ms,
    }
    row["error_category"] = classify_error(row)
    return row


# ------------------------------------------------------------------ aggregation
def summarize_rows(rows: list[dict]) -> dict:
    n = len(rows)
    exp_tpl = [r for r in rows if r["expected_route"] == "retriever"]
    exp_llm = [r for r in rows if r["expected_route"] == "llm"]
    tpl_routed = [r for r in rows if r["route"] == "retriever"]
    llm_routed = [r for r in rows if r["route"] == "llm"]
    failures = [r for r in rows if r["error_category"]]

    retrieval = {
        "expected_template_questions": len(exp_tpl),
        "top1_is_expected_template_pct": _pct(sum(1 for r in exp_tpl if r["retrieval_top1_ok"]), len(exp_tpl)),
        "expected_template_in_topk_pct": _pct(sum(1 for r in exp_tpl if r["retrieval_topk_ok"]), len(exp_tpl)),
        "top1_above_threshold_pct": _pct(sum(1 for r in rows if r["top1_similarity"] >= RAG_SIMILARITY_THRESHOLD), n),
        "avg_top1_similarity": _avg([r["top1_similarity"] for r in rows], 3),
        "avg_top1_similarity_expected_llm": _avg([r["top1_similarity"] for r in exp_llm], 3),
    }
    routing = {
        "routing_accuracy_pct": _pct(sum(r["route_ok"] for r in rows), n),
        "template_route_recall_pct": _pct(sum(r["route_ok"] and r["template_ok"] for r in exp_tpl), len(exp_tpl)),
        "llm_route_accuracy_pct": _pct(sum(r["route_ok"] for r in exp_llm), len(exp_llm)),
        "template_route_precision_pct": _pct(sum(r["route_ok"] and r["template_ok"] for r in tpl_routed), len(tpl_routed)),
        "false_positive_template": sum(1 for r in tpl_routed if r["expected_route"] != "retriever"),
        "wrong_template_chosen": sum(1 for r in tpl_routed if r["expected_route"] == "retriever" and not r["template_ok"]),
        "false_negative_template": sum(1 for r in exp_tpl if r["route"] != "retriever"),
        "guard_forced_llm": sum(1 for r in rows if r["guard_reason"]),
    }
    execution = {
        "sql_generated_pct": _pct(sum(1 for r in rows if r["pred_sql"]), n),
        "execution_success_pct": _pct(sum(1 for r in rows if r["executed"]), n),
        "firewall_blocks": sum(r["firewall_blocks"] for r in rows),
        "sql_errors": sum(r["sql_errors"] for r in rows),
        "blocked_or_no_sql": sum(1 for r in rows if not r["pred_sql"]),
    }
    results = {
        "strict_accuracy_pct": _pct(sum(r["strict_match"] for r in rows), n),
        "lenient_accuracy_pct": _pct(sum(r["lenient_match"] for r in rows), n),
        "strict_accuracy_template_route_pct": _pct(sum(r["strict_match"] for r in tpl_routed), len(tpl_routed)),
        "strict_accuracy_llm_route_pct": _pct(sum(r["strict_match"] for r in llm_routed), len(llm_routed)),
        "strict_accuracy_expected_llm_pct": _pct(sum(r["strict_match"] for r in exp_llm), len(exp_llm)),
        "strict_accuracy_non_ambiguous_pct": _pct(sum(r["strict_match"] for r in rows if "ambiguous" not in r["tags"]),
                                                  sum(1 for r in rows if "ambiguous" not in r["tags"])),
    }
    reflection = {
        "questions_with_reflection": sum(1 for r in rows if r["reflections"]),
        "reflection_rate_pct": _pct(sum(1 for r in rows if r["reflections"]), n),
        "reflect_llm_calls": sum(r["llm_reflect_calls"] for r in rows),
        "recovered_after_reflection": sum(1 for r in rows if r["reflections"] and r["strict_match"]),
    }
    llm_usage = {
        "sql_calls": sum(r["llm_sql_calls"] for r in rows),
        "reflect_calls": sum(r["llm_reflect_calls"] for r in rows),
        "explain_calls": sum(r["llm_explain_calls"] for r in rows),
        "planner_calls": sum(r.get("llm_planner_calls") or 0 for r in rows),
        "total_calls": sum(r["llm_calls"] for r in rows),
        "calls_per_query": _avg([r["llm_calls"] for r in rows], 2),
        "questions_without_llm_pct": _pct(sum(1 for r in rows if r["llm_calls"] == 0), n),
        "total_tokens": sum(r["llm_tokens"] for r in rows),
    }
    simple_rows = [r for r in rows if not r.get("is_complex")]
    complex_rows = [r for r in rows if r.get("is_complex")]
    planner_ok = [r for r in complex_rows if r.get("planner_success")]
    step_exec = [r for r in complex_rows if (r.get("steps_total") or 0) and r.get("steps_ok") == r.get("steps_total")]
    analytical = {
        "simple_queries": len(simple_rows),
        "complex_queries": len(complex_rows),
        "multi_step_trigger_rate": _pct(sum(1 for r in rows if r.get("multi_step")), n),
        "planner_success_rate": _pct(len(planner_ok), len(complex_rows)),
        "step_execution_success": _pct(len(step_exec), len(complex_rows)),
        "final_result_success": _pct(sum(1 for r in complex_rows if r.get("executed") or (r.get("multi_step") and not r.get("error"))), len(complex_rows)),
        "average_latency": _avg([r["latency_ms"] for r in rows]),
        "average_cost": round(sum(r["cost_usd"] for r in rows) / n, 6) if n else None,
        "simple_avg_latency_ms": _avg([r["latency_ms"] for r in simple_rows]),
        "complex_avg_latency_ms": _avg([r["latency_ms"] for r in complex_rows]),
        "simple_avg_cost_usd": round(sum(r["cost_usd"] for r in simple_rows) / len(simple_rows), 6) if simple_rows else None,
        "complex_avg_cost_usd": round(sum(r["cost_usd"] for r in complex_rows) / len(complex_rows), 6) if complex_rows else None,
        "simple_planner_calls": sum(r.get("llm_planner_calls") or 0 for r in simple_rows),
    }
    template_usage = {
        "template_hits": len(tpl_routed),
        "template_hit_rate_pct": _pct(len(tpl_routed), n),
        "per_template": dict(Counter(r["template_id"] for r in tpl_routed).most_common()),
    }
    latency = {
        "avg_ms": _avg([r["latency_ms"] for r in rows]),
        "p50_ms": _percentile([r["latency_ms"] for r in rows], 0.5),
        "p95_ms": _percentile([r["latency_ms"] for r in rows], 0.95),
        "avg_template_route_ms": _avg([r["latency_ms"] for r in tpl_routed]),
        "avg_llm_route_ms": _avg([r["latency_ms"] for r in llm_routed]),
    }
    cost = {
        "total_usd": round(sum(r["cost_usd"] for r in rows), 5),
        "avg_per_query_usd": round(sum(r["cost_usd"] for r in rows) / n, 6) if n else None,
    }
    error_breakdown = {cat: 0 for cat in ERROR_CATEGORIES}
    error_breakdown.update(Counter(r["error_category"] for r in failures))
    tags = sorted({t for r in rows for t in r["tags"]})
    by_tag = {}
    for tag in tags:
        subset = [r for r in rows if tag in r["tags"]]
        by_tag[tag] = {"n": len(subset), "routing_pct": _pct(sum(r["route_ok"] for r in subset), len(subset)),
                       "strict_pct": _pct(sum(r["strict_match"] for r in subset), len(subset))}
    return {
        "n": n, "retrieval": retrieval, "routing": routing, "execution": execution, "results": results,
        "reflection": reflection, "llm_usage": llm_usage, "template_usage": template_usage,
        "latency": latency, "cost": cost, "error_breakdown": error_breakdown,
        "errors": [{"id": r["id"], "question": r["question"], "category": r["error_category"], "route": r["route"],
                    "template_id": r["template_id"], "detail": (r["error"] or r["guard_reason"] or "")[:200]}
                   for r in failures],
        "by_tag": by_tag,
        "analytical": analytical,
    }


COMPARISON_METRICS = [
    ("routing_accuracy_pct", ("routing", "routing_accuracy_pct")),
    ("template_route_precision_pct", ("routing", "template_route_precision_pct")),
    ("false_positive_template", ("routing", "false_positive_template")),
    ("false_negative_template", ("routing", "false_negative_template")),
    ("execution_success_pct", ("execution", "execution_success_pct")),
    ("strict_accuracy_pct", ("results", "strict_accuracy_pct")),
    ("lenient_accuracy_pct", ("results", "lenient_accuracy_pct")),
    ("strict_accuracy_non_ambiguous_pct", ("results", "strict_accuracy_non_ambiguous_pct")),
    ("wrong_template_routing_errors", ("error_breakdown", "wrong_template_routing")),
    ("template_hits", ("template_usage", "template_hits")),
    ("llm_total_calls", ("llm_usage", "total_calls")),
    ("llm_sql_calls", ("llm_usage", "sql_calls")),
    ("reflect_calls", ("llm_usage", "reflect_calls")),
    ("avg_latency_ms", ("latency", "avg_ms")),
    ("p95_latency_ms", ("latency", "p95_ms")),
    ("avg_cost_usd", ("cost", "avg_per_query_usd")),
    ("total_cost_usd", ("cost", "total_usd")),
]


def compare_modes(summaries: dict) -> dict:
    """baseline vs improved side-by-side (delta = improved - baseline)."""
    if not {"baseline", "improved"} <= set(summaries):
        return {}
    out = {}
    for name, (section, key) in COMPARISON_METRICS:
        b, i = summaries["baseline"][section].get(key), summaries["improved"][section].get(key)
        delta = round(i - b, 6) if isinstance(b, (int, float)) and isinstance(i, (int, float)) else None
        out[name] = {"baseline": b, "improved": i, "delta": delta}
    return out


def print_summary(mode: str, s: dict) -> None:
    print(f"\n===== {mode.upper()} (n={s['n']}) =====")
    for section in ("retrieval", "routing", "execution", "results", "reflection", "llm_usage", "latency", "cost", "analytical"):
        print(f"{section:<14}", json.dumps(s[section], ensure_ascii=False))
    print(f"{'templates':<14}", json.dumps({k: v for k, v in s["template_usage"].items() if k != "per_template"}))
    print(f"{'errors':<14}", json.dumps(s["error_breakdown"]))


def print_comparison(comparison: dict) -> None:
    if not comparison:
        return
    print("\n===== BASELINE (similarity only) vs IMPROVED (similarity + compatibility) =====")
    print(f"{'metric':<36}{'baseline':>12}{'improved':>12}{'delta':>12}")
    for name, v in comparison.items():
        fmt = lambda x: "-" if x is None else (f"{x:.5f}" if isinstance(x, float) and abs(x) < 1 else f"{x:g}")
        print(f"{name:<36}{fmt(v['baseline']):>12}{fmt(v['improved']):>12}{fmt(v['delta']):>12}")


def check_complexity_labels(items: list[dict]) -> list[dict]:
    """Detector-only check (no LLM, no database)."""
    rows = []
    for item in items:
        got = detect_complexity(item["question"])
        ok = got.is_complex == bool(item["expected_complex"])
        rows.append({
            "id": item["id"], "question": item["question"],
            "expected_complex": item["expected_complex"], "got_complex": got.is_complex,
            "analysis_type": got.analysis_type, "reasons": got.reasons, "ok": ok,
        })
        flag = "PASS" if ok else "FAIL"
        print(f"[{flag}] detector {item['id']} expected={item['expected_complex']} got={got.is_complex} {item['question']}")
    return rows


def run_analytical_one(item: dict) -> dict:
    clear_caches()
    before = len(get_events())
    started = time.time()
    result = run_question(item["question"])
    latency_ms = round((time.time() - started) * 1000)
    events = get_events()[before:]
    llm_calls = [e for e in events if e.get("type") == "llm_call"]
    pred_df = result.get("dataframe")
    pred_df = pred_df if isinstance(pred_df, pd.DataFrame) else pd.DataFrame()
    complete = next((e for e in reversed(events) if e.get("type") == "analysis_complete"), {})
    row = {
        "id": item["id"], "question": item["question"],
        "expected_complex": item["expected_complex"],
        "is_complex": detect_complexity(item["question"]).is_complex,
        "route": result.get("route_taken"),
        "multi_step": result.get("route_taken") == "multi_step",
        "planner_calls": sum(1 for e in llm_calls if e.get("node") == "planner"),
        "planner_success": any(e.get("type") in {"planner_success", "planner_fallback"} for e in events),
        "analysis_plan": result.get("analysis_plan"),
        "step_results": result.get("step_results") or [],
        "steps_ok": complete.get("steps_ok"),
        "steps_total": complete.get("steps_total"),
        "fetch_ok": complete.get("fetch_ok"),
        "fetch_total": complete.get("fetch_total"),
        "error": result.get("error"),
        "row_count": int(len(pred_df)),
        "explanation": (result.get("explanation") or "")[:400],
        "llm_calls": len(llm_calls),
        "planner_llm_calls": sum(1 for e in llm_calls if e.get("node") == "planner"),
        "sql_llm_calls": sum(1 for e in llm_calls if e.get("node") in {"sql", "sql_reflect"}),
        "final_llm_calls": sum(1 for e in llm_calls if e.get("node") in {"explain", "synthesis"}),
        "deterministic_steps": complete.get("deterministic_steps"),
        "db_queries": complete.get("db_queries") or (result.get("analysis_telemetry") or {}).get("db_queries"),
        "llm_latency_ms": round(sum(float(e.get("latency_ms") or 0) for e in llm_calls), 2),
        "db_latency_ms": complete.get("db_latency_ms") or (result.get("analysis_telemetry") or {}).get("db_latency_ms"),
        "llm_tokens": sum(int(e.get("total_tokens") or 0) for e in llm_calls),
        "cost_usd": round(sum(float(e.get("estimated_cost") or 0) for e in llm_calls), 6),
        "latency_ms": latency_ms,
        "analysis_telemetry": result.get("analysis_telemetry"),
    }
    if item["expected_complex"]:
        step_ok = bool(row["steps_total"]) and row["steps_ok"] == row["steps_total"]
        row["trigger_ok"] = row["multi_step"] and row["planner_calls"] >= 1
        row["planner_ok"] = row["planner_success"]
        row["step_execution_ok"] = step_ok
        row["final_ok"] = row["multi_step"] and not row["error"] and row["row_count"] > 0
    else:
        row["trigger_ok"] = (not row["multi_step"]) and row["planner_calls"] == 0
        row["planner_ok"] = row["planner_calls"] == 0
        row["step_execution_ok"] = True
        row["final_ok"] = not row["error"]
    return row


def summarize_analytical_examples(rows: list[dict]) -> dict:
    simple = [r for r in rows if not r["expected_complex"]]
    complex_ = [r for r in rows if r["expected_complex"]]
    n = len(rows)
    return {
        "simple_queries": len(simple),
        "complex_queries": len(complex_),
        "multi_step_trigger_rate": _pct(sum(1 for r in rows if r["multi_step"]), n),
        "detector_accuracy_pct": _pct(sum(1 for r in rows if r["is_complex"] == r["expected_complex"]), n),
        "planner_success_rate": _pct(sum(1 for r in complex_ if r["planner_ok"]), len(complex_)),
        "step_execution_success": _pct(sum(1 for r in complex_ if r["step_execution_ok"]), len(complex_)),
        "final_result_success": _pct(sum(1 for r in complex_ if r["final_ok"]), len(complex_)),
        "simple_fast_path_ok": all(r["trigger_ok"] for r in simple) if simple else None,
        "simple_planner_calls": sum(r["planner_calls"] for r in simple),
        "average_latency": _avg([r["latency_ms"] for r in rows]),
        "average_cost": round(sum(r["cost_usd"] for r in rows) / n, 6) if n else None,
        "simple_avg_latency_ms": _avg([r["latency_ms"] for r in simple]),
        "complex_avg_latency_ms": _avg([r["latency_ms"] for r in complex_]),
        "simple_avg_cost_usd": round(sum(r["cost_usd"] for r in simple) / len(simple), 6) if simple else None,
        "complex_avg_cost_usd": round(sum(r["cost_usd"] for r in complex_) / len(complex_), 6) if complex_ else None,
        "complex_avg_llm_calls": _avg([r["llm_calls"] for r in complex_], 2),
        "complex_avg_planner_llm_calls": _avg([r.get("planner_llm_calls") or r["planner_calls"] for r in complex_], 2),
        "complex_avg_sql_llm_calls": _avg([r.get("sql_llm_calls") or 0 for r in complex_], 2),
        "complex_avg_final_llm_calls": _avg([r.get("final_llm_calls") or 0 for r in complex_], 2),
        "complex_avg_db_queries": _avg([r.get("db_queries") or 0 for r in complex_], 2),
    }


def evaluate_analytical(path: Path = ANALYTICAL_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["items"] if isinstance(data, dict) else data
    print(f"\n--- complexity detector ({len(items)} analytical examples) ---")
    detector_rows = check_complexity_labels(items)
    print(f"\n--- analytical examples (agent) ---")
    set_routing_mode("improved")
    rows = []
    for item in items:
        row = run_analytical_one(item)
        rows.append(row)
        flag = "PASS" if row["trigger_ok"] and row["final_ok"] else "FAIL"
        print(f"[{flag}] {row['id']} route={row['route']} planner={row['planner_calls']} "
              f"sql_llm={row.get('sql_llm_calls')} db={row.get('db_queries')} "
              f"steps={row['steps_ok']}/{row['steps_total']} {row['latency_ms']}ms ${row['cost_usd']} {row['question']}")
    summary = summarize_analytical_examples(rows)
    print("analytical     ", json.dumps(summary, ensure_ascii=False))
    return {"detector": detector_rows, "rows": rows, "summary": summary}


# ------------------------------------------------------------------ evaluation
def evaluate(out_path: Path, gold_path: Path = GOLD_PATH, modes: tuple[str, ...] = ("improved", "baseline"),
             analytical: bool = True, gold: bool = True) -> dict:
    items, version = load_gold(gold_path)
    if not is_available():
        raise SystemExit("FAISS index missing - run scripts/build_index.py first")

    per_mode_rows: dict[str, list[dict]] = {}
    summaries: dict[str, dict] = {}
    if gold:
        for mode in modes:
            set_routing_mode(mode)
            clear_caches()
            reset_events()
            print(f"\n--- routing mode: {mode} | gold set {version} ({len(items)} questions) ---")
            rows = []
            for item in items:
                row = run_one(item)
                rows.append(row)
                flag = "PASS" if row["strict_match"] else ("~" if row["lenient_match"] else "FAIL")
                route_flag = "" if row["route_ok"] else f" (expected {row['expected_route']})"
                cat = f" [{row['error_category']}]" if row["error_category"] else ""
                print(f"[{flag}] #{row['id']:>2} {str(row['route']):<9} sim={row['top1_similarity']:.3f} "
                      f"tpl={row['template_id'] or '-':<24} rows={row['pred_rows']}/{row['gold_rows']}{route_flag}{cat} {row['question']}")
            per_mode_rows[mode] = rows
            summaries[mode] = summarize_rows(rows)
        set_routing_mode("improved")

    comparison = compare_modes(summaries)
    analytical_report = evaluate_analytical() if analytical else None
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "gold_set": {"path": str(gold_path.relative_to(PROJECT_ROOT)) if gold_path.is_relative_to(PROJECT_ROOT) else str(gold_path),
                     "version": version, "n": len(items)},
        "threshold": RAG_SIMILARITY_THRESHOLD,
        "modes": summaries,
        "comparison": comparison,
        "rows": per_mode_rows,
        "analytical_examples": analytical_report,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    for mode in modes:
        if mode in summaries:
            print_summary(mode, summaries[mode])
    print_comparison(comparison)
    print("\nreport:", out_path)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(REPORT_DIR / "latest.json"))
    parser.add_argument("--gold", default=str(GOLD_PATH), help="gold set JSON (v1 list or v2 {items:[...]})")
    parser.add_argument("--modes", default="improved,baseline", help="comma-separated: improved,baseline")
    parser.add_argument("--analytical-only", action="store_true", help="skip gold set; run analytical examples only")
    parser.add_argument("--skip-analytical", action="store_true", help="skip the small analytical example set")
    args = parser.parse_args()
    evaluate(
        Path(args.out),
        Path(args.gold),
        tuple(m.strip() for m in args.modes.split(",") if m.strip()),
        analytical=not args.skip_analytical,
        gold=not args.analytical_only,
    )
