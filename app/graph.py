"""Supervisor LangGraph.

plan -> supervisor -> research | data | code -> supervisor -> summary.
The supervisor reads the plan. It does not inspect the question text.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.code import code_node
from app.agents.data import data_node
from app.agents.research import research_node
from app.agents.summary import summary_node
from app.json_util import extract_json
from app.prompts import PLANNER_PROMPT
from app.routing import run_task
from app.state import AgentState
from app.trace_util import trace_event

ALLOWED_AGENTS = {"research", "data", "code"}
ALLOWED_KINDS = {"lookup", "code", "synthesis", "rewrite", "plan", "summary"}


def _fallback_plan() -> list[dict]:
    return [
        {
            "id": "s1",
            "agent": "research",
            "reason": "Planner output was not valid, so the graph falls back to a single research step.",
            "depends_on": [],
            "complexity": "low",
            "kind": "lookup",
            "status": "pending",
        }
    ]


def _validate_plan(payload) -> list[dict] | None:
    steps = payload.get("steps") if isinstance(payload, dict) else payload
    if not isinstance(steps, list) or not steps or len(steps) > 3:
        return None
    cleaned = []
    seen = set()
    for index, raw in enumerate(steps, start=1):
        if not isinstance(raw, dict):
            return None
        agent = raw.get("agent")
        complexity = raw.get("complexity")
        kind = raw.get("kind", "lookup")
        if agent not in ALLOWED_AGENTS or complexity not in {"low", "high"} or kind not in ALLOWED_KINDS:
            return None
        step_id = str(raw.get("id") or f"s{index}")
        if step_id in seen:
            return None
        seen.add(step_id)
        depends = raw.get("depends_on") or []
        if not isinstance(depends, list) or any(not isinstance(item, str) for item in depends):
            return None
        cleaned.append(
            {
                "id": step_id,
                "agent": agent,
                "reason": str(raw.get("reason") or "The planner selected this worker.").strip(),
                "depends_on": depends,
                "complexity": complexity,
                "kind": kind,
                "status": "pending",
            }
        )
    earlier: set[str] = set()
    for step in cleaned:
        if any(dep not in earlier for dep in step["depends_on"]):
            return None
        earlier.add(step["id"])
    return cleaned


def plan_node(state: dict) -> dict:
    entry = trace_event("plan", "enter", "write plan")
    routes: list[dict] = []
    history = state.get("history") or []
    result = run_task(
        {
            "agent": "planner",
            "complexity": "low",
            "kind": "plan",
            "prompt": f"{PLANNER_PROMPT}\n\nHistory: {history}\n\nQuestion: {state['user_query']}",
        },
        routes,
    )
    events = [entry]
    plan = None
    if result["ok"]:
        try:
            plan = _validate_plan(extract_json(result["text"]))
        except Exception:
            plan = None
    if plan is None:
        plan = _fallback_plan()
        events.append(trace_event("plan", "fallback", "invalid planner JSON; using one research step"))
    events.append(trace_event("plan", "exit", ",".join(step["agent"] for step in plan)))
    return {"plan": plan, "route_log": routes, "trace": events}


def supervisor_node(state: dict) -> dict:
    plan = [dict(step) for step in state.get("plan") or []]
    by_id = {step["id"]: step for step in plan}
    for step in plan:
        if step["status"] != "pending":
            continue
        missing = [dep for dep in step["depends_on"] if dep not in by_id or dep == step["id"]]
        if missing:
            step["status"] = "failed"
            continue
        if all(by_id[dep]["status"] in {"done", "failed"} for dep in step["depends_on"]):
            step["status"] = "running"
            return {
                "plan": plan,
                "next_node": step["agent"],
                "current_step_id": step["id"],
                "trace": [
                    trace_event(
                        "supervisor",
                        "route",
                        f"next={step['agent']} id={step['id']} reason={step['reason']}",
                    )
                ],
            }
    return {
        "plan": plan,
        "next_node": "summary",
        "trace": [trace_event("supervisor", "route", "planned steps are finished; next=summary")],
    }


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("research", research_node)
    graph.add_node("data", data_node)
    graph.add_node("code", code_node)
    graph.add_node("summary", summary_node)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        lambda state: state["next_node"],
        {"research": "research", "data": "data", "code": "code", "summary": "summary"},
    )
    graph.add_edge("research", "supervisor")
    graph.add_edge("data", "supervisor")
    graph.add_edge("code", "supervisor")
    graph.add_edge("summary", END)
    return graph.compile()


def initial_state(question: str, history: list[dict] | None = None) -> dict:
    return {
        "user_query": question,
        "history": history or [],
        "plan": [],
        "route_log": [],
        "agent_outputs": {},
        "citations": [],
        "errors": [],
        "trace": [],
        "final_answer": "",
        "next_node": "",
        "current_step_id": "",
    }
