"""Pull a JSON object or array out of a model response."""

from __future__ import annotations

import json
import re


def extract_json(text: str):
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        for opener, closer in (("{", "}"), ("[", "]")):
            start = cleaned.find(opener)
            end = cleaned.rfind(closer)
            if start >= 0 and end > start:
                return json.loads(cleaned[start : end + 1])
        raise
