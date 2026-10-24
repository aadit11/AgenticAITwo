"""Trace events and plan-step updates shared by the graph nodes."""

from __future__ import annotations

from datetime import datetime, timezone


def trace_event(node: str, event: str, detail: str) -> dict:
    return {
        "node": node,
        "event": event,
        "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def mark_step(plan: list[dict], step_id: str, status: str) -> list[dict]:
    updated = []
    for step in plan:
        item = dict(step)
        if item["id"] == step_id:
            item["status"] = status
        updated.append(item)
    return updated
