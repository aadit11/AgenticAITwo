"""Code agent. Tools: search_code and read_file, limited to code_bundle/."""

from __future__ import annotations

import json

from app.json_util import extract_json
from app.prompts import CODE_PROMPT
from app.routing import run_task
from app.trace_util import mark_step, trace_event
from tools.code_reader import read_file, search_code


def code_node(state: dict) -> dict:
    step = _step(state)
    entry = trace_event("code", "enter", step["id"])
    routes: list[dict] = []
    errors: list[dict] = []
    try:
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
        matches = search_code(query, limit=5)
        if hinted:
            matches = [item for item in matches if item["path"] == hinted] or matches
        if not matches:
            text = "No matching line was found in code_bundle/."
        else:
            hit = matches[0]
            snippet = read_file(hit["path"], max(hit["line"] - 2, 1), hit["line"] + 12)
            explained = run_task(
                {
                    "agent": "code",
                    "complexity": "high",
                    "kind": "code",
                    "prompt": (
                        f"{CODE_PROMPT}\n\nExplain this code and cite path:line.\n\n"
                        f"Question: {state['user_query']}\n\n{snippet['path']}\n{snippet['text']}"
                    ),
                },
                routes,
            )
            text = explained["text"] if explained["ok"] else snippet["text"]
        status = "done"
    except Exception as exc:
        text = "Code could not read the bundle."
        status = "failed"
        errors.append({"agent": "code", "message": type(exc).__name__, "recovered": False})
    return {
        "plan": mark_step(state["plan"], step["id"], status),
        "agent_outputs": {step["id"]: text},
        "route_log": routes,
        "errors": errors,
        "trace": [entry, trace_event("code", "exit", status)],
    }


def _step(state: dict) -> dict:
    for step in state["plan"]:
        if step["id"] == state["current_step_id"]:
            return step
    raise KeyError(state.get("current_step_id"))
