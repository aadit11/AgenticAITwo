"""Prove Research and Summary share one Tavily MCP server with different arguments."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agents.research import needs_live_web
from app.agents.summary import research_urls
from app.graph import build_graph, initial_state

QUESTIONS = [
    "What PEPs were accepted after the corpus snapshot date?",
    "What does PEP 8 say about imports, and which pages discuss Python PEPs since the corpus snapshot date?",
]


def tool_details(trace: list[dict], node: str, prefix: str) -> list[str]:
    return [
        event["detail"]
        for event in trace
        if event["node"] == node and event["event"] == "tool" and str(event["detail"]).startswith(prefix)
    ]


def assert_local_rules() -> None:
    if needs_live_web("What does PEP 8 say about imports?", 0.7):
        raise SystemExit("a strong corpus hit should not search the web")
    if not needs_live_web("What does PEP 8 say about imports?", 0.2):
        raise SystemExit("a weak corpus hit should search the web")
    if not needs_live_web("What PEPs were accepted after the corpus snapshot date?", 0.9):
        raise SystemExit("a post-snapshot question should search the web")
    urls = research_urls(
        [
            {"chunk_id": "pep-0008/09-imports/0", "source": "https://peps.python.org/pep-0008/"},
            {"chunk_id": "tavily-search:0", "source": "https://example.com/peps"},
        ]
    )
    if urls != ["https://example.com/peps"]:
        raise SystemExit(f"summary picked the wrong URL: {urls}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    assert_local_rules()
    graph = build_graph()
    runs = []
    shared = False
    for question in QUESTIONS:
        print(f"\n=== {question}", flush=True)
        state = graph.invoke(initial_state(question), config={"recursion_limit": 40})
        trace = state["trace"]
        searches = tool_details(trace, "research", "tavily_search query=")
        extracts = tool_details(trace, "summary", "tavily_extract urls=")
        print("SEARCH", searches, flush=True)
        print("EXTRACT", extracts, flush=True)
        print("ANSWER", state["final_answer"], flush=True)
        if not state["final_answer"].strip():
            raise SystemExit("graph finished without a final answer")
        blob = json.dumps({"trace": trace, "answer": state["final_answer"]})
        if "tavilyApiKey" in blob or "TAVILY_API_KEY" in blob:
            raise SystemExit("the trace contains the Tavily key")
        if searches and extracts and searches[0] != extracts[0]:
            shared = True
        runs.append(
            {
                "question": question,
                "plan": state["plan"],
                "final_answer": state["final_answer"],
                "search": searches,
                "extract": extracts,
                "trace": trace,
            }
        )
    if not shared:
        raise SystemExit("no query showed both Tavily search and Tavily extract")
    destination = ROOT / "eval" / "phase5_runs.json"
    destination.write_text(json.dumps(runs, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {destination}", flush=True)


if __name__ == "__main__":
    main()
