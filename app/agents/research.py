"""Research agent. Tool: Chroma retriever. Tavily search is added in Phase 5."""

from __future__ import annotations

from app.prompts import RESEARCH_PROMPT
from app.routing import run_task
from app.trace_util import mark_step, trace_event
from tools.chroma_retriever import retrieve


def research_node(state: dict) -> dict:
    step = _step(state)
    entry = trace_event("research", "enter", step["id"])
    routes: list[dict] = []
    errors: list[dict] = []
    citations: list[dict] = []
    try:
        rewritten = run_task(
            {
                "agent": "research",
                "complexity": "low",
                "kind": "rewrite",
                "prompt": (
                    "Rewrite the question as a short search query that would appear in a Python document. "
                    "Output the query only.\n\nQuestion: "
                    + state["user_query"]
                ),
            },
            routes,
        )
        search_query = rewritten["text"].strip().splitlines()[0][:300] if rewritten["ok"] else state["user_query"]
        citations = _merge_citations(retrieve(search_query, k=5), retrieve(state["user_query"], k=5))
        passages = "\n\n".join(
            f"[{item['chunk_id']}] {item['title']} / {item['section']}\n{item['excerpt']}"
            for item in citations
        )
        result = run_task(
            {
                "agent": "research",
                "complexity": step["complexity"],
                "kind": step["kind"],
                "prompt": f"{RESEARCH_PROMPT}\n\nPassages:\n{passages}\n\nQuestion: {state['user_query']}",
            },
            routes,
        )
        text = result["text"] if result["ok"] else "Research could not produce an answer."
        status = "done" if result["ok"] else "failed"
        if not result["ok"]:
            errors.append({"agent": "research", "message": "provider failed", "recovered": False})
    except Exception as exc:
        text = "Research failed before it could answer."
        status = "failed"
        errors.append({"agent": "research", "message": type(exc).__name__, "recovered": False})
    return {
        "plan": mark_step(state["plan"], step["id"], status),
        "agent_outputs": {step["id"]: text},
        "citations": citations,
        "route_log": routes,
        "errors": errors,
        "trace": [entry, trace_event("research", "exit", status)],
    }


def _merge_citations(primary: list[dict], extra: list[dict]) -> list[dict]:
    by_id = {item["chunk_id"]: item for item in primary}
    for item in extra:
        current = by_id.get(item["chunk_id"])
        if current is None or item["score"] > current["score"]:
            by_id[item["chunk_id"]] = item
    return sorted(by_id.values(), key=lambda item: item["score"], reverse=True)[:5]


def _step(state: dict) -> dict:
    for step in state["plan"]:
        if step["id"] == state["current_step_id"]:
            return step
    raise KeyError(state.get("current_step_id"))
