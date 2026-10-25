"""Data agent. Tool: read-only SQLite SELECT over data/peps.sqlite."""

from __future__ import annotations

import json

from app.json_util import extract_json
from app.prompts import DATA_PROMPT
from app.routing import run_task
from app.trace_util import mark_step, recovered_error, trace_event
from tools.sqlite_tool import query_database


def data_node(state: dict) -> dict:
    step_id = str(state.get("current_step_id") or "")
    entry = trace_event("data", "enter", step_id)
    routes: list[dict] = []
    errors: list[dict] = []
    try:
        step = _step(state)
        step_id = step["id"]
        drafted = run_task(
            {
                "agent": "data",
                "complexity": step["complexity"],
                "kind": step["kind"],
                "prompt": f"{DATA_PROMPT}\n\nQuestion: {state['user_query']}",
            },
            routes,
        )
        if not drafted["ok"]:
            raise RuntimeError("sql generation failed")
        sql = extract_json(drafted["text"])["sql"]
        result = query_database(sql)
        text = "SQL: {sql}\nRows: {rows}".format(sql=result["sql"], rows=json.dumps(result["rows"]))
        status = "done"
    except Exception as exc:
        text = "Data could not answer from the PEP table."
        status = "failed"
        errors.append(recovered_error("data", type(exc).__name__))
    return {
        "plan": mark_step(state["plan"], step_id, status),
        "agent_outputs": {step_id: text},
        "route_log": routes,
        "errors": errors,
        "trace": [entry, trace_event("data", "exit", status)],
    }


def _step(state: dict) -> dict:
    for step in state["plan"]:
        if step["id"] == state["current_step_id"]:
            return step
    raise KeyError(state.get("current_step_id"))
