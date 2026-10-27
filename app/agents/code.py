"""Code agent. Tools: search_code and read_file, limited to code_bundle/."""

from __future__ import annotations

import json
import re

from app.json_util import extract_json
from app.prompts import CODE_PROMPT
from app.routing import run_task
from app.trace_util import mark_step, recovered_error, trace_event
from tools.code_reader import read_file, search_code

_SKIP_NAMES = {
    "about",
    "allow",
    "bundle",
    "code",
    "does",
    "from",
    "function",
    "guide",
    "import",
    "into",
    "lines",
    "module",
    "negative",
    "number",
    "python",
    "return",
    "source",
    "string",
    "style",
    "table",
    "that",
    "this",
    "what",
    "when",
    "where",
    "which",
    "with",
}


def code_node(state: dict) -> dict:
    step_id = str(state.get("current_step_id") or "")
    entry = trace_event("code", "enter", step_id)
    routes: list[dict] = []
    errors: list[dict] = []
    try:
        step = _step(state)
        step_id = step["id"]
        located = run_task(
            {
                "agent": "code",
                "complexity": step["complexity"],
                "kind": "code",
                "prompt": (
                    f"{CODE_PROMPT}\n\nFind the function or file for this question. "
                    f"Output JSON only.\n\nQuestion: {state['user_query']}"
                ),
            },
            routes,
        )
        if not located["ok"]:
            raise RuntimeError("code search planning failed")
        try:
            request = extract_json(located["text"])
            query = str(request.get("query") or state["user_query"])
            hinted = str(request.get("path") or "")
        except (json.JSONDecodeError, TypeError, AttributeError):
            query = state["user_query"]
            hinted = ""
        shown = _relevant_source(state["user_query"], query, hinted)
        if not shown:
            text = "No matching line was found in code_bundle/."
        else:
            explained = run_task(
                {
                    "agent": "code",
                    "complexity": "high",
                    "kind": "code",
                    "prompt": (
                        f"{CODE_PROMPT}\n\nExplain this code and cite path:line.\n\n"
                        f"Question: {state['user_query']}\n\n{shown}"
                    ),
                },
                routes,
            )
            text = explained["text"] if explained["ok"] else shown
        status = "done"
    except Exception as exc:
        text = "Code could not read the bundle."
        status = "failed"
        errors.append(recovered_error("code", type(exc).__name__))
    return {
        "plan": mark_step(state["plan"], step_id, status),
        "agent_outputs": {step_id: text},
        "route_log": routes,
        "errors": errors,
        "trace": [entry, trace_event("code", "exit", status)],
    }


def _function_names(*texts: str) -> list[str]:
    found = []
    for text in texts:
        for name in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\b", text):
            if name.lower() in _SKIP_NAMES or name in found:
                continue
            found.append(name)
    return found


def _find_definition(name: str) -> dict | None:
    try:
        matches = search_code(f"def {name}", limit=10)
    except ValueError:
        return None
    pattern = re.compile(rf"^\s*def {re.escape(name)}\b")
    for item in matches:
        if pattern.search(item["text"]):
            return item
    return None


def _relevant_source(question: str, query: str, hinted: str) -> str:
    """Read the file that defines the named function, then any helper it calls.

    A match in pep_tools/__init__.py is only a re-export, so it is not enough.
    """
    files: list[str] = []
    if hinted and not hinted.endswith("__init__.py"):
        files.append(hinted)
    seen_names = set()
    for name in _function_names(question, query):
        seen_names.add(name)
        hit = _find_definition(name)
        if hit and hit["path"] not in files:
            files.append(hit["path"])
    chunks = []
    for path in files[:4]:
        try:
            snippet = read_file(path, 1, 200)
        except (OSError, ValueError, FileNotFoundError):
            continue
        chunks.append(f"{snippet['path']}\n{snippet['text']}")
        for callee in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\s*\(", snippet["text"]):
            if callee in seen_names or callee.lower() in _SKIP_NAMES:
                continue
            seen_names.add(callee)
            extra = _find_definition(callee)
            if extra and extra["path"] not in files and len(files) < 4:
                files.append(extra["path"])
    if chunks:
        return "\n\n".join(chunks)
    try:
        matches = search_code(query, limit=8)
    except ValueError:
        return ""
    if hinted:
        matches = [item for item in matches if item["path"] == hinted] or matches
    matches = [item for item in matches if not item["path"].endswith("__init__.py")] or matches
    if not matches:
        return ""
    hit = matches[0]
    snippet = read_file(hit["path"], max(hit["line"] - 2, 1), hit["line"] + 40)
    return f"{snippet['path']}\n{snippet['text']}"


def _step(state: dict) -> dict:
    for step in state["plan"]:
        if step["id"] == state["current_step_id"]:
            return step
    raise KeyError(state.get("current_step_id"))
