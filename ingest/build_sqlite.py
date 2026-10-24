"""Build data/peps.sqlite from the PEP header blocks already downloaded in corpus/."""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

FIELD = re.compile(r"^([A-Za-z][A-Za-z0-9-]*)\s*:\s*(.*)$")
PEP_FILE = re.compile(r"^pep-(\d+)\.rst$")


def pep_dir() -> Path:
    matches = sorted((ROOT / "corpus" / "peps-src").glob("peps-*/peps"))
    if not matches:
        raise FileNotFoundError("PEP sources were not extracted. Run ingest/download_corpus.py.")
    return matches[0]


def sqlite_path() -> Path:
    configured = Path(os.environ.get("SQLITE_PATH", "./data/peps.sqlite"))
    if not configured.is_absolute():
        configured = ROOT / configured
    configured.parent.mkdir(parents=True, exist_ok=True)
    return configured


def parse_header(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current: str | None = None
    started = False
    for line in text.splitlines():
        if not line.strip():
            if started:
                break
            continue
        if line[0].isspace():
            if current:
                fields[current] = f"{fields[current]} {line.strip()}".strip()
            continue
        match = FIELD.match(line)
        if not match:
            break
        started = True
        current = match.group(1)
        fields[current] = match.group(2).strip()
    return fields


def load_rows() -> list[tuple]:
    rows = []
    for path in sorted(pep_dir().glob("pep-*.rst")):
        match = PEP_FILE.match(path.name)
        if not match:
            continue
        header = parse_header(path.read_text(encoding="utf-8", errors="replace"))
        number = int(match.group(1))
        rows.append(
            (
                number,
                header.get("Title") or f"PEP {number}",
                header.get("Status") or None,
                header.get("Type") or None,
                header.get("Created") or None,
                header.get("Python-Version") or None,
                header.get("Author") or None,
            )
        )
    return rows


def independent_final_count() -> int:
    """Count Status: Final from the raw header, without using the database."""
    total = 0
    for path in pep_dir().glob("pep-*.rst"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            if line.startswith("==="):
                break
            if line.startswith("Status:"):
                if line.split(":", 1)[1].strip() == "Final":
                    total += 1
                break
    return total


def main() -> None:
    rows = load_rows()
    destination = sqlite_path()
    if destination.exists():
        destination.unlink()
    connection = sqlite3.connect(destination)
    connection.execute(
        """
        CREATE TABLE peps (
            number INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT,
            type TEXT,
            created TEXT,
            python_version TEXT,
            author TEXT
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO peps (number, title, status, type, created, python_version, author)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.commit()
    db_final = connection.execute("SELECT COUNT(*) FROM peps WHERE status = 'Final'").fetchone()[0]
    hand_final = independent_final_count()
    connection.close()
    print(f"rows={len(rows)} path={destination}")
    print(f"status_final db={db_final} header_scan={hand_final}")
    if db_final != hand_final:
        raise SystemExit("Final count from the database does not match the header scan")


if __name__ == "__main__":
    main()
