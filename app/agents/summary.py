"""Summary agent. Merges worker outputs and extracts a page Research already found."""

from __future__ import annotations

import json

from app.prompts import SUMMARY_PROMPT
from app.publish import sink_bound
from app.routing import complete, run_task, stream_complete
from app.trace_util import recovered_error, trace_event
from tools.tavily_mcp import tavily_extract


def summary_node(state: dict) -> dict:
    entry = trace_event("summary", "enter", "merge")
    routes: list[dict] = []
    errors: list[dict] = []
    tool_events: list[dict] = []
    outputs = json.dumps(state.get("agent_outputs") or {}, indent=2)
    citations = state.get("citations") or []
    history = json.dumps(state.get("history") or [], indent=2)
    failures = json.dumps(state.get("errors") or [], indent=2)
    extracted = _extract_research_url(citations, errors, tool_events)
    try:
        result = run_task(
            {
                "agent": "summary",
                "complexity": "high",
                "kind": "summary",
                "prompt": (
                    f"{SUMMARY_PROMPT}\n\nHistory:\n{history}\n\n"
                    f"Question: {state['user_query']}\n\nWorker outputs:\n{outputs}\n\n"
                    f"Citations:\n{json.dumps(citations, indent=2)}\n\n"
                    f"Errors:\n{failures}\n\n"
                    f"Extracted page:\n{extracted or 'None.'}"
                ),
            },
            routes,
            caller=stream_complete if sink_bound() else complete,
        )
        text = result["text"] if result["ok"] else "Summary could not merge the worker outputs."
        if not result["ok"]:
            errors.append(recovered_error("summary", "provider failed"))
    except Exception as exc:
        text = "Summary failed before it could merge the worker outputs."
        errors.append(recovered_error("summary", type(exc).__name__))
    return {
        "final_answer": text,
        "route_log": routes,
        "errors": errors,
        "trace": [entry, *tool_events, trace_event("summary", "exit", "done" if text else "failed")],
    }


def research_urls(citations: list[dict]) -> list[str]:
    """URLs that Research returned from Tavily search. Corpus source links are ignored."""
    urls = []
    for item in citations:
        if not str(item.get("chunk_id", "")).startswith("tavily-search:"):
            continue
        url = str(item.get("source") or "")
        if url.startswith("http") and url not in urls:
            urls.append(url)
    return urls


def _extract_research_url(citations: list[dict], errors: list[dict], tool_events: list[dict]) -> str:
    urls = research_urls(citations)
    if not urls:
        return ""
    target = urls[0]
    try:
        found = tavily_extract([target])
    except Exception as exc:
        errors.append(recovered_error("summary", f"tavily_extract {type(exc).__name__}"))
        tool_events.append(trace_event("summary", "tool", f"tavily_extract failed {type(exc).__name__}"))
        return ""
    tool_events.append(trace_event("summary", "tool", f"tavily_extract urls={target}"))
    return found["content"]
