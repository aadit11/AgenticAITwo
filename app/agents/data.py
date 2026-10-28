"""Data agent. Tool: read-only SQLite SELECT over data/peps.sqlite."""

from __future__ import annotations

import json
import re
import sqlite3

from app.json_util import extract_json
from app.prompts import DATA_PROMPT
from app.routing import run_task
from app.trace_util import mark_step, recovered_error, trace_event
from tools.sqlite_tool import query_database

_SELECT = re.compile(r"(?is)\b(?:select|with)\b[\s\S]+?(?:;|$)")


def data_node(state: dict) -> dict:
    step_id = str(state.get("current_step_id") or "")
    entry = trace_event(
        "data",
        "enter",
        f"Starting {step_id or 'the data step'}. Data writes one read-only SELECT and runs it on the PEP table.",
    )
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
        try:
            result = _query_reply(drafted["text"])
            problem = _version_problem(state["user_query"], result["sql"])
            if problem:
                raise ValueError(problem)
        except (json.JSONDecodeError, TypeError, AttributeError, ValueError, KeyError, sqlite3.Error) as exc:
            versions = re.findall(r"\b\d+\.\d+\b", state["user_query"])
            if versions:
                clauses = " OR ".join(f"python_version LIKE '%{version}%'" for version in versions)
                result = query_database(f"SELECT COUNT(*) AS n FROM peps WHERE {clauses}")
            else:
                retried = run_task(
                    {
                        "agent": "data",
                        "complexity": step["complexity"],
                        "kind": step["kind"],
                        "prompt": (
                            f"{DATA_PROMPT}\n\nThe previous reply failed ({type(exc).__name__}: {exc}). "
                            "Output one JSON object only. Use the column python_version, not Python-Version.\n\n"
                            f"Question: {state['user_query']}"
                        ),
                    },
                    routes,
                )
                if not retried["ok"]:
                    raise RuntimeError("sql generation failed")
                result = _query_reply(retried["text"])
        text = "SQL: {sql}\nRows: {rows}".format(sql=result["sql"], rows=json.dumps(result["rows"]))
        query_note = trace_event(
            "data",
            "query",
            f"Ran `{result['sql']}`. The table returned {len(result['rows'])} row(s).",
        )
        status = "done"
    except Exception as exc:
        text = "Data could not answer from the PEP table."
        query_note = None
        status = "failed"
        errors.append(recovered_error("data", type(exc).__name__))
    exit_detail = (
        "Finished. The rows go back to the supervisor."
        if status == "done"
        else "Data failed. The supervisor will still continue, and Summary will name the failure."
    )
    traces = [entry]
    if query_note:
        traces.append(query_note)
    traces.append(trace_event("data", "exit", exit_detail))
    return {
        "plan": mark_step(state["plan"], step_id, status),
        "agent_outputs": {step_id: text},
        "route_log": routes,
        "errors": errors,
        "trace": traces,
    }


def _version_problem(question: str, sql: str) -> str:
    missing = [item for item in re.findall(r"\b\d+\.\d+\b", question) if item not in sql]
    if not missing:
        return ""
    versions = ", ".join(missing)
    return f"the question asks for version {versions}, but the SQL does not filter for it"


def _query_reply(text: str) -> dict:
    return query_database(_sql_from_text(text))


def _sql_from_text(text: str) -> str:
    try:
        payload = extract_json(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and payload.get("sql"):
        return str(payload["sql"])
    match = _SELECT.search(text or "")
    if not match:
        raise ValueError("no SQL statement in the model reply")
    return match.group(0).strip().rstrip(";").strip()


def _step(state: dict) -> dict:
    for step in state["plan"]:
        if step["id"] == state["current_step_id"]:
            return step
    raise KeyError(state.get("current_step_id"))
