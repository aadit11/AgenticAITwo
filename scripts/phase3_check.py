"""Run the five Phase 3 starter questions through the supervisor graph."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.graph import build_graph, initial_state

QUESTIONS = [
    "What does PEP 8 say about imports?",
    "How many PEPs in the table have status Final?",
    "Show the function format_pep_reference in code_bundle/pep_tools/references.py and explain it.",
    "What PEPs were accepted after the corpus snapshot date?",
    "Combine a PEP 8 import rule with the count of PEPs whose type is Process, and write one paragraph.",
]


def signature(plan: list[dict]) -> str:
    brief = [
        {
            "agent": step["agent"],
            "kind": step["kind"],
            "complexity": step["complexity"],
            "depends_on": step["depends_on"],
            "reason": step["reason"],
        }
        for step in plan
    ]
    return json.dumps(brief, sort_keys=True)


def main() -> None:
    graph = build_graph()
    runs = []
    for question in QUESTIONS:
        print(f"\n=== {question}", flush=True)
        state = graph.invoke(initial_state(question), config={"recursion_limit": 40})
        plan = state["plan"]
        print("PLAN", json.dumps(plan, indent=2), flush=True)
        print("TRACE", json.dumps(state["trace"], indent=2), flush=True)
        print("ANSWER", state["final_answer"], flush=True)
        nodes = [event["node"] for event in state["trace"]]
        if "supervisor" not in nodes or "summary" not in nodes:
            raise SystemExit("trace is missing the supervisor or the summary")
        if not state["final_answer"].strip():
            raise SystemExit("graph finished without a final answer")
        worker_exits = [event for event in state["trace"] if event["event"] == "exit" and event["node"] in {"research", "data", "code"}]
        if not worker_exits:
            raise SystemExit("no worker returned")
        runs.append({"question": question, "plan": plan, "signature": signature(plan), "final_answer": state["final_answer"], "trace": state["trace"]})
    signatures = [run["signature"] for run in runs]
    if len(set(signatures)) != len(QUESTIONS):
        raise SystemExit(f"plans were not all different: {signatures}")
    destination = ROOT / "eval" / "phase3_runs.json"
    destination.write_text(json.dumps(runs, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {destination}", flush=True)


if __name__ == "__main__":
    main()
