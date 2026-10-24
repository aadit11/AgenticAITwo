"""Read the RFC-style header at the top of a PEP file."""

from __future__ import annotations

import re

FIELD = re.compile(r"^([A-Za-z][A-Za-z0-9-]*)\s*:\s*(.*)$")


def parse_pep_header(text: str) -> dict[str, str]:
    """Return header fields. Continuation lines are joined with a space."""
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
