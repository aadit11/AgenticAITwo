"""LangGraph state schema."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


def merge_dicts(left: dict | None, right: dict | None) -> dict:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class AgentState(TypedDict):
    user_query: str
    history: list[dict]
    plan: list[dict]
    route_log: Annotated[list[dict], operator.add]
    agent_outputs: Annotated[dict, merge_dicts]
    citations: Annotated[list[dict], operator.add]
    errors: Annotated[list[dict], operator.add]
    trace: Annotated[list[dict], operator.add]
    final_answer: str
    next_node: str
    current_step_id: str
