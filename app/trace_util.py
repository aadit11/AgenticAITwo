"""Trace events and plan-step updates shared by the graph nodes."""

from __future__ import annotations

from datetime import datetime, timezone

from app.publish import publish


def trace_event(node: str, event: str, detail: str) -> dict:
    payload = {
        "node": node,
        "event": event,
        "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    publish("trace", {"node": node, "event": event, "detail": detail})
    return payload


def recovered_error(agent: str, message: str) -> dict:
    """An error that stayed inside the graph. The message says the failure was recovered."""
    detail = message.strip() or "worker failed"
    if "failure was recovered" not in detail:
        detail = f"{detail}; the failure was recovered"
    payload = {"agent": agent, "message": detail, "recovered": True}
    publish("error", payload)
    return payload


def mark_step(plan: list[dict], step_id: str, status: str) -> list[dict]:
    updated = []
    for step in plan:
        item = dict(step)
        if item["id"] == step_id:
            item["status"] = status
        updated.append(item)
    return updated
