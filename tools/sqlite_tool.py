"""Read-only SQL tool. Data is the only agent that uses this tool."""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DEFAULT_LIMIT = 50
FORBIDDEN = re.compile(
    r"(?i)\b(insert|update|delete|drop|alter|attach|detach|pragma|vacuum|reindex|create|replace|load_extension)\b"
)


def database_path() -> Path:
    configured = Path(os.environ.get("SQLITE_PATH", "./data/peps.sqlite"))
    if not configured.is_absolute():
        configured = ROOT / configured
    return configured


def _validate(sql: str) -> str:
    statement = sql.strip()
    if statement.endswith(";"):
        statement = statement[:-1].strip()
    if not statement:
        raise ValueError("SQL statement is empty")
    if ";" in statement:
        raise ValueError("only one SELECT statement is allowed")
    if not re.match(r"(?is)^(select|with)\b", statement):
        raise ValueError("only SELECT statements are allowed")
    if FORBIDDEN.search(statement):
        raise ValueError("statement is not read-only")
    return statement


def _allow_read(action, arg1, arg2, db_name, source):
    allowed = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_RECURSIVE,
    }
    if action in allowed:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def query_database(sql: str, limit: int = DEFAULT_LIMIT) -> dict:
    """Run one SELECT and return the SQL plus at most `limit` rows."""
    statement = _validate(sql)
    if limit < 1:
        raise ValueError("limit must be at least 1")
    path = database_path()
    if not path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {path}")
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.set_authorizer(_allow_read)
    try:
        cursor = connection.execute(statement)
        fetched = cursor.fetchmany(limit + 1)
    finally:
        connection.close()
    truncated = len(fetched) > limit
    visible = fetched[:limit]
    columns = list(visible[0].keys()) if visible else []
    rows = [dict(row) for row in visible]
    return {
        "sql": statement,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }
