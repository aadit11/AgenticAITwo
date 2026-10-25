"""Live events for one chat request. Unbound calls do nothing."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Callable

Sink = Callable[[str, dict], None]
_sink: ContextVar[Sink | None] = ContextVar("sse_sink", default=None)


def bind_sink(sink: Sink) -> Token:
    return _sink.set(sink)


def reset_sink(token: Token) -> None:
    _sink.reset(token)


def sink_bound() -> bool:
    return _sink.get() is not None


def publish(kind: str, payload: dict) -> None:
    sink = _sink.get()
    if sink is not None:
        sink(kind, payload)


def publish_citation(item: dict) -> None:
    publish(
        "citation",
        {
            "chunk_id": item.get("chunk_id", ""),
            "source": item.get("source", ""),
            "title": item.get("title", ""),
            "section": item.get("section", ""),
            "score": item.get("score", 0),
            "excerpt": item.get("excerpt", ""),
        },
    )
