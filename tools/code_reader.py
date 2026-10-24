"""Sandboxed code search and file read under code_bundle/.

Code is the only agent that uses this tool.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

TEXT_SUFFIXES = {".py", ".txt", ".md", ".rst", ".toml"}
MAX_MATCHES = 20


def bundle_root() -> Path:
    configured = Path(os.environ.get("CODE_BUNDLE_DIR", "./code_bundle"))
    if not configured.is_absolute():
        configured = ROOT / configured
    return configured.resolve()


def _inside_bundle(path: Path) -> Path:
    root = bundle_root()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("path escapes code_bundle")
    return resolved


def search_code(query: str, limit: int = MAX_MATCHES) -> list[dict]:
    """Return lines inside code_bundle that contain query."""
    needle = query.strip()
    if not needle:
        raise ValueError("query is empty")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    root = bundle_root()
    matches: list[dict] = []
    lowered = needle.lower()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if lowered in line.lower():
                matches.append({"path": relative, "line": number, "text": line.rstrip()})
                if len(matches) >= limit:
                    return matches
    return matches


def read_file(path: str, start: int = 1, end: int | None = None) -> dict:
    """Return a 1-based inclusive line range. Paths cannot leave code_bundle."""
    if start < 1:
        raise ValueError("start must be at least 1")
    if end is not None and end < start:
        raise ValueError("end must be greater than or equal to start")
    candidate = Path(path)
    if candidate.is_absolute():
        resolved = _inside_bundle(candidate)
    else:
        resolved = _inside_bundle(bundle_root() / candidate)
    if not resolved.is_file():
        raise FileNotFoundError(path)
    lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
    last = len(lines) if end is None else min(end, len(lines))
    selected = lines[start - 1 : last]
    numbered = [f"{start + offset}|{text}" for offset, text in enumerate(selected)]
    relative = resolved.relative_to(bundle_root()).as_posix()
    return {
        "path": relative,
        "start": start,
        "end": start + len(selected) - 1 if selected else start - 1,
        "text": "\n".join(numbered),
    }
