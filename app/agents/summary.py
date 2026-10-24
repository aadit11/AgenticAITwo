"""Summary agent. Merges worker outputs and keeps their citations.

Tavily extract is added in Phase 5.
"""

from __future__ import annotations

import json

from app.prompts import SUMMARY_PROMPT
from app.routing import run_task
from app.trace_util import trace_event


def summary_node(state: dict) -> dict:
    entry = trace_event("summary", "enter", "merge")
    routes: list[dict] = []
    errors: list[dict] = []
    outputs = json.dumps(state.get("agent_outputs") or {}, indent=2)
    citations = json.dumps(state.get("citations") or [], indent=2)
    history = json.dumps(state.get("history") or [], indent=2)
    try:
        result = run_task(
            {
                "agent": "summary",
                "complexity": "high",
                "kind": "summary",
                "prompt": (
                    f"{SUMMARY_PROMPT}\n\nHistory:\n{history}\n\n"
                    f"Question: {state['user_query']}\n\nWorker outputs:\n{outputs}\n\n"
                    f"Citations:\n{citations}"
                ),
            },
            routes,
        )
        text = result["text"] if result["ok"] else "Summary could not merge the worker outputs."
        if not result["ok"]:
            errors.append({"agent": "summary", "message": "provider failed", "recovered": False})
    except Exception as exc:
        text = "Summary failed before it could merge the worker outputs."
        errors.append({"agent": "summary", "message": type(exc).__name__, "recovered": False})
    return {
        "final_answer": text,
        "route_log": routes,
        "errors": errors,
        "trace": [entry, trace_event("summary", "exit", "done" if text else "failed")],
    }
