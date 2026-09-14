"""SQL firewall: static analysis of generated SQL before it reaches PostgreSQL.

Checks (all must pass):
  1. single statement, no comments, size cap
  2. parses as a SELECT (CTEs allowed) - no DML/DDL, no locking, no SELECT INTO
  3. every physical table is in the allow-list (CTE names excluded), no system catalogs
  4. every referenced column is a real column of `orders` or an alias defined in the query
  5. no dangerous / side-effecting functions
  6. LIMIT is capped to MAX_RESULT_ROWS (appended when missing)
"""
import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from src.config import ALLOWED_TABLES, MAX_RESULT_ROWS, MAX_SQL_CHARS
from src.db.schema import SCHEMA_COLUMNS

DANGEROUS_FUNCTIONS = {
    "pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file",
    "lo_import", "lo_export", "dblink", "dblink_connect", "copy", "exec", "execute",
    "set_config", "current_setting", "pg_terminate_backend", "pg_cancel_backend",
    "query_to_xml", "xmlparse", "pg_reload_conf", "format", "pg_advisory_lock",
}
SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}
FORBIDDEN_TOKENS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|vacuum|analyze|"
    r"call|do|listen|notify|refresh|reindex|cluster|lock|into|for\s+update|for\s+share)\b",
    re.IGNORECASE,
)


@dataclass
class FirewallResult:
    ok: bool
    message: str
    sql: str | None = None


def _collect_aliases(tree: exp.Expression) -> set[str]:
    names: set[str] = set()
    for alias in tree.find_all(exp.Alias):
        if alias.alias:
            names.add(alias.alias.lower())
    for cte in tree.find_all(exp.CTE):
        if cte.alias_or_name:
            names.add(cte.alias_or_name.lower())
        if isinstance(cte.this, exp.Select):
            for proj in cte.this.expressions:
                if proj.alias_or_name:
                    names.add(proj.alias_or_name.lower())
    for sub in tree.find_all(exp.Subquery):
        if sub.alias:
            names.add(sub.alias.lower())
    return names


def sql_firewall(sql: str) -> FirewallResult:
    if not sql or not sql.strip():
        return FirewallResult(False, "Empty SQL")
    cleaned = sql.strip().rstrip(";").strip()

    if len(cleaned) > MAX_SQL_CHARS:
        return FirewallResult(False, "SQL too long")
    if ";" in cleaned:
        return FirewallResult(False, "Multi-statement queries are blocked")
    if "--" in cleaned or "/*" in cleaned:
        return FirewallResult(False, "SQL comments are blocked")

    # Keyword scan on the text outside string literals.
    no_literals = re.sub(r"'(?:[^']|'')*'", "''", cleaned)
    if FORBIDDEN_TOKENS.search(no_literals):
        return FirewallResult(False, "Only read-only SELECT statements are allowed")

    try:
        tree = sqlglot.parse_one(cleaned, read="postgres")
    except Exception as exc:
        return FirewallResult(False, f"Parse error: {exc}")

    if not isinstance(tree, (exp.Select, exp.Union)):
        return FirewallResult(False, "Only SELECT statements are allowed")
    if tree.args.get("locks"):
        return FirewallResult(False, "Row locking is blocked")

    # Tables
    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE) if c.alias_or_name}
    for table in tree.find_all(exp.Table):
        if table.db and table.db.lower() in SYSTEM_SCHEMAS:
            return FirewallResult(False, "System catalogs are blocked")
        name = table.name.lower()
        if name in cte_names:
            continue
        if name.startswith("pg_") or name not in ALLOWED_TABLES:
            return FirewallResult(False, f"Unauthorized table: {table.name}")

    # Columns
    allowed_cols = SCHEMA_COLUMNS | _collect_aliases(tree)
    for col in tree.find_all(exp.Column):
        name = col.name.lower()
        if name and name not in allowed_cols:
            return FirewallResult(False, f"Unknown column: {col.name}")

    # Functions
    for func in tree.find_all(exp.Func):
        fname = (func.sql_name() if not isinstance(func, exp.Anonymous) else str(func.this)).lower()
        if fname in DANGEROUS_FUNCTIONS:
            return FirewallResult(False, f"Blocked function: {fname}")
    for cmd in tree.find_all(exp.Command):
        return FirewallResult(False, f"Blocked command: {cmd.sql()[:40]}")

    # LIMIT cap
    limit = tree.args.get("limit")
    if limit is not None and isinstance(limit.expression, exp.Literal):
        try:
            if int(limit.expression.this) > MAX_RESULT_ROWS:
                tree.set("limit", exp.Limit(expression=exp.Literal.number(MAX_RESULT_ROWS)))
        except ValueError:
            return FirewallResult(False, "Invalid LIMIT")
    elif limit is None and isinstance(tree, exp.Select):
        tree.set("limit", exp.Limit(expression=exp.Literal.number(MAX_RESULT_ROWS)))

    return FirewallResult(True, "OK", tree.sql(dialect="postgres"))
