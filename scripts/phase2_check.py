"""Phase 2 checks. No network calls."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code_bundle"))

from ingest.build_sqlite import independent_final_count
from tools.code_reader import read_file, search_code
from tools.sqlite_tool import query_database


def expect_raise(label: str, func) -> None:
    try:
        func()
    except (ValueError, FileNotFoundError):
        print(f"rejected {label}")
        return
    raise SystemExit(f"expected {label} to be rejected")


def main() -> None:
    result = query_database("SELECT COUNT(*) AS n FROM peps WHERE status = 'Final'")
    db_count = result["rows"][0]["n"]
    hand_count = independent_final_count()
    print(f"final_count sql={db_count} header_scan={hand_count} sql_text={result['sql']}")
    if db_count != hand_count:
        raise SystemExit("SQL count does not match the header scan")
    if result["sql"] != "SELECT COUNT(*) AS n FROM peps WHERE status = 'Final'":
        raise SystemExit("SQL text was not returned unchanged")

    pep8 = query_database("SELECT number, title, status, author FROM peps WHERE number = 8")
    print(pep8["rows"][0])
    if pep8["rows"][0]["status"] != "Active":
        raise SystemExit("PEP 8 status was not Active")

    expect_raise("delete", lambda: query_database("DELETE FROM peps"))
    expect_raise("stacked statement", lambda: query_database("SELECT 1; DROP TABLE peps"))

    matches = search_code("def format_pep_reference")
    if not matches or matches[0]["path"] != "pep_tools/references.py":
        raise SystemExit(f"search_code missed format_pep_reference: {matches}")
    start = matches[0]["line"]
    snippet = read_file("pep_tools/references.py", start, start + 3)
    print(snippet["text"])
    if "def format_pep_reference" not in snippet["text"]:
        raise SystemExit("read_file did not return the expected function")
    if snippet["start"] != start:
        raise SystemExit("read_file start line does not match the search hit")

    expect_raise("path escape", lambda: read_file("../.env", 1, 3))
    expect_raise("absolute escape", lambda: read_file(str(ROOT / ".env"), 1, 3))
    print("phase 2 checks passed")


if __name__ == "__main__":
    main()
