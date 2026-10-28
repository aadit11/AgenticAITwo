"""Research agent. Tools: Chroma retriever, and Tavily search on the shared MCP server."""

from __future__ import annotations

import time

from app.prompts import RESEARCH_PROMPT
from app.publish import publish_citation
from app.routing import run_task
from app.trace_util import mark_step, recovered_error, trace_event
from tools.chroma_retriever import _named_pep_ids, retrieve
from tools.tavily_mcp import tavily_search

SNAPSHOT = "2026-10-24"
WEAK_SCORE = 0.5
PEP_DOMAINS = ["peps.python.org", "discuss.python.org", "blog.python.org"]


def research_node(state: dict) -> dict:
    step_id = str(state.get("current_step_id") or "")
    entry = trace_event(
        "research",
        "enter",
        f"Starting {step_id or 'the research step'}. Research rewrites the question, searches the corpus, and answers from those passages.",
    )
    routes: list[dict] = []
    errors: list[dict] = []
    citations: list[dict] = []
    tool_events: list[dict] = []
    extra_traces: list[dict] = []
    try:
        step = _step(state)
        step_id = step["id"]
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
        started = time.perf_counter()
        citations = _merge_citations(
            retrieve(search_query, k=5),
            retrieve(state["user_query"], k=5),
            state["user_query"],
        )
        retrieve_ms = round((time.perf_counter() - started) * 1000, 1)
        best = max(citations, key=lambda item: item["score"], default=None)
        best_note = (
            f" Best match is {best['chunk_id']} in {best['title']}, score {best['score']:.3f}."
            if best
            else " No passages were returned."
        )
        web_needed = needs_live_web(state["user_query"], best["score"] if best else 0.0)
        web_note = (
            " A web search will run because the corpus match is weak or the question is after the snapshot."
            if web_needed
            else " No web search: the corpus match is strong enough and the question is inside the snapshot."
        )
        extra_traces.append(
            trace_event(
                "research",
                "retrieve",
                f"Corpus search took {retrieve_ms} ms and kept {len(citations)} passages.{best_note}{web_note}",
            )
        )
        web_passages, tool_events = _maybe_search(state["user_query"], citations, errors)
        for item in citations:
            publish_citation(item)
        passages = "\n\n".join(
            f"[{item['chunk_id']}] {item['title']} / {item['section']}\n{item.get('text') or item['excerpt']}"
            for item in citations
            if not str(item["chunk_id"]).startswith("tavily-search:")
        )
        result = run_task(
            {
                "agent": "research",
                "complexity": step["complexity"],
                "kind": step["kind"],
                "prompt": (
                    f"{RESEARCH_PROMPT}\n\nPassages:\n{passages}\n\n"
                    f"Web results:\n{web_passages or 'None.'}\n\nQuestion: {state['user_query']}"
                ),
            },
            routes,
        )
        text = result["text"] if result["ok"] else "Research could not produce an answer."
        status = "done" if result["ok"] else "failed"
        if not result["ok"]:
            errors.append(recovered_error("research", "provider failed"))
    except Exception as exc:
        text = "Research failed before it could answer."
        status = "failed"
        errors.append(recovered_error("research", type(exc).__name__))
    return {
        "plan": mark_step(state["plan"], step_id, status),
        "agent_outputs": {step_id: text},
        "citations": citations,
        "route_log": routes,
        "errors": errors,
        "trace": [
            entry,
            *extra_traces,
            *tool_events,
            trace_event(
                "research",
                "exit",
                "Finished. The notes go back to the supervisor."
                if status == "done"
                else "Research failed. The supervisor will still continue, and Summary will name the failure.",
            ),
        ],
    }


def _merge_citations(primary: list[dict], extra: list[dict], question: str) -> list[dict]:
    by_id = {item["chunk_id"]: item for item in primary}
    for item in extra:
        current = by_id.get(item["chunk_id"])
        if current is None or item["score"] > current["score"]:
            by_id[item["chunk_id"]] = item
    ranked = sorted(by_id.values(), key=lambda item: item["score"], reverse=True)
    named_ids = _named_pep_ids(question)
    if named_ids:
        named = [
            item
            for item in extra
            if any(item["chunk_id"].startswith(f"{doc_id}/") for doc_id in named_ids)
        ]
        if named:
            return named[:6]
    return ranked[:5]


def needs_live_web(question: str, best_score: float) -> bool:
    """Search the live web when the corpus is a poor match or the question is after the snapshot."""
    text = question.lower()
    after_snapshot = any(
        phrase in text
        for phrase in (
            "after the corpus snapshot",
            "after the snapshot",
            "since the corpus snapshot",
            "since the snapshot",
            "newer than the snapshot",
            "after 2026-10-24",
        )
    )
    return after_snapshot or best_score < WEAK_SCORE


def _maybe_search(question: str, citations: list[dict], errors: list[dict]) -> tuple[str, list[dict]]:
    best = max((item["score"] for item in citations), default=0.0)
    if not needs_live_web(question, best):
        return "", []
    after_snapshot = "snapshot" in question.lower() or SNAPSHOT in question
    query = "Python PEPs accepted" if after_snapshot else question[:300]
    domains = PEP_DOMAINS if after_snapshot else None
    try:
        found = tavily_search(query, include_domains=domains, max_results=3)
        if after_snapshot and not found["results"]:
            found = tavily_search(query, max_results=3)
    except Exception as exc:
        errors.append(recovered_error("research", f"tavily_search {type(exc).__name__}"))
        return "", [trace_event("research", "tool", f"tavily_search failed {type(exc).__name__}")]
    lines = []
    for index, item in enumerate(found["results"]):
        citations.append(
            {
                "chunk_id": f"tavily-search:{index}",
                "source": item["url"],
                "title": item["title"],
                "section": "web",
                "score": 0.0,
                "excerpt": item["content"],
            }
        )
        lines.append(f"{item['url']}\n{item['title']}\n{item['content']}")
    detail = (
        f"tavily_search query={found['arguments']['query']}. "
        f"Research called the shared Tavily search tool and got {len(found['results'])} results."
    )
    return "\n\n".join(lines), [trace_event("research", "tool", detail)]


def _step(state: dict) -> dict:
    for step in state["plan"]:
        if step["id"] == state["current_step_id"]:
            return step
    raise KeyError(state.get("current_step_id"))
