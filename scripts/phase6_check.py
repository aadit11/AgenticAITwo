"""Phase 6 failure check. A broken Data step still reaches Summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.agents.data as data_mod
import app.graph as graph_mod
from app.graph import invoke_graph, supervisor_node
from app.trace_util import mark_step, trace_event

QUESTION = "What does PEP 8 say about imports, and how many PEPs have status Final?"


def _step(step_id: str, agent: str, depends_on: list[str], status: str) -> dict:
    return {
        "id": step_id,
        "agent": agent,
        "reason": f"{agent} step {step_id}",
        "depends_on": depends_on,
        "complexity": "low",
        "kind": "lookup",
        "status": status,
    }


def assert_recovered(errors: list[dict], agent: str) -> None:
    matches = [item for item in errors if item.get("agent") == agent and item.get("recovered") is True]
    if not matches or not any("failure was recovered" in item.get("message", "") for item in matches):
        raise SystemExit(f"{agent} error does not say the failure was recovered: {errors}")


def check_supervisor() -> dict:
    skipped = supervisor_node(
        {
            "plan": [
                _step("s1", "data", [], "failed"),
                _step("s2", "code", ["s1"], "pending"),
            ]
        }
    )
    if skipped["next_node"] != "summary":
        raise SystemExit(f"a failed data step should send the graph to summary, got {skipped['next_node']}")
    if skipped["plan"][1]["status"] != "failed":
        raise SystemExit("the code step that depends on data was not skipped")
    assert_recovered(skipped["errors"], "code")

    continued = supervisor_node(
        {
            "plan": [
                _step("s1", "data", [], "failed"),
                _step("s2", "code", ["s1"], "pending"),
                _step("s3", "research", [], "pending"),
            ]
        }
    )
    if continued["next_node"] != "research" or continued["current_step_id"] != "s3":
        raise SystemExit(f"an independent step should still run, got {continued}")
    if continued["plan"][1]["status"] != "failed":
        raise SystemExit("skipping a dependent step also blocked an independent step")
    print("supervisor: skipped the dependent code step and kept research runnable", flush=True)
    return skipped


def check_graph_guard() -> dict:
    def explode(state):
        raise RuntimeError("planner exploded")

    original = graph_mod.plan_node
    graph_mod.plan_node = explode
    try:
        result = invoke_graph("hello", graph=graph_mod.build_graph())
    finally:
        graph_mod.plan_node = original
    assert_recovered(result["errors"], "graph")
    if "failure was recovered" not in result["final_answer"]:
        raise SystemExit(f"graph guard did not return an error payload: {result['final_answer']}")
    print("graph guard: planner exception became an error payload", flush=True)
    return {"errors": result["errors"], "final_answer": result["final_answer"]}


def fixed_plan(state):
    return {
        "plan": [
            _step("s1", "research", [], "pending"),
            _step("s2", "data", [], "pending"),
            _step("s3", "code", ["s2"], "pending"),
        ],
        "route_log": [],
        "trace": [trace_event("plan", "exit", "research,data,code")],
    }


def canned_research(state):
    step_id = state["current_step_id"]
    return {
        "plan": mark_step(state["plan"], step_id, "done"),
        "agent_outputs": {step_id: "Imports are usually on separate lines. [pep-0008/09-imports/0]"},
        "citations": [],
        "trace": [trace_event("research", "exit", "done")],
    }


def forced_data_failure(*args, **kwargs):
    raise RuntimeError("forced data failure")


def check_broken_data() -> dict:
    original_plan = graph_mod.plan_node
    original_research = graph_mod.research_node
    original_run_task = data_mod.run_task
    graph_mod.plan_node = fixed_plan
    graph_mod.research_node = canned_research
    data_mod.run_task = forced_data_failure
    try:
        result = invoke_graph(QUESTION, graph=graph_mod.build_graph())
    finally:
        graph_mod.plan_node = original_plan
        graph_mod.research_node = original_research
        data_mod.run_task = original_run_task

    answer = result["final_answer"]
    print("ANSWER", answer, flush=True)
    print("ERRORS", json.dumps(result["errors"], indent=2), flush=True)
    if not answer.strip():
        raise SystemExit("broken data did not produce a summary answer")
    assert_recovered(result["errors"], "data")
    statuses = {step["id"]: step["status"] for step in result["plan"]}
    if statuses.get("s1") != "done" or statuses.get("s2") != "failed" or statuses.get("s3") != "failed":
        raise SystemExit(f"unexpected plan statuses: {statuses}")
    nodes = [event["node"] for event in result["trace"]]
    if "code" in nodes:
        raise SystemExit("the code step ran after its data dependency failed")
    if "summary" not in nodes:
        raise SystemExit("summary did not run")
    lowered = answer.lower()
    if "pep-0008/09-imports/0" not in answer and "separate lines" not in lowered:
        raise SystemExit("summary dropped the research result")
    if not any(word in lowered for word in ("data", "count", "missing", "could not", "failed", "unavailable")):
        raise SystemExit("summary did not say what the data failure left missing")
    return {
        "question": QUESTION,
        "plan": result["plan"],
        "errors": result["errors"],
        "final_answer": answer,
        "trace": result["trace"],
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    supervisor = check_supervisor()
    guard = check_graph_guard()
    broken = check_broken_data()
    destination = ROOT / "eval" / "phase6_runs.json"
    destination.write_text(
        json.dumps({"supervisor_skip": supervisor, "graph_guard": guard, "broken_data": broken}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {destination}", flush=True)


if __name__ == "__main__":
    main()
