"""Provider selection and one-retry fallback.

The plan step sets complexity to low or high. This module reads that field.
It does not inspect the user question.
"""

from __future__ import annotations

import os
import time
from contextvars import ContextVar
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from google import genai
from google.genai import types
from openai import OpenAI

from app.publish import publish
from app.trace_util import trace_event

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

_last_tokens: ContextVar[tuple[int, int] | None] = ContextVar("last_tokens", default=None)

COST_MODEL_ENV = "GEMINI_MODEL"
CAPABILITY_MODEL_ENV = "OPENAI_MODEL"
DEFAULT_COST_MODEL = "gemini-3.8-flash"
DEFAULT_CAPABILITY_MODEL = "gpt-6.1-sol"

Complete = Callable[[dict, str, bool], str]


def _model(env_name: str, default: str) -> str:
    return os.environ.get(env_name, default).strip() or default


def choose_provider(task: dict) -> dict:
    """Pick a provider from the plan fields on `task`.

    task requires agent, complexity ("low" or "high"), and kind
    (plan, rewrite, lookup, synthesis, summary, or code).
    """
    complexity = task.get("complexity")
    kind = task.get("kind", "lookup")
    agent = task.get("agent", "research")
    if complexity not in {"low", "high"}:
        raise ValueError("task complexity must be low or high")
    if complexity == "high":
        return {
            "agent": agent,
            "provider": "openai",
            "model": _model(CAPABILITY_MODEL_ENV, DEFAULT_CAPABILITY_MODEL),
            "dimension": "capability",
            "reason": f"Complexity is high for this {kind} step, so the more capable model handles it.",
            "kind": kind,
        }
    return {
        "agent": agent,
        "provider": "google",
        "model": _model(COST_MODEL_ENV, DEFAULT_COST_MODEL),
        "dimension": "cost",
        "reason": f"Complexity is low for this {kind} step, so the cheaper model handles it.",
        "kind": kind,
    }


def alternate_provider(decision: dict, error_name: str) -> dict:
    if decision["provider"] == "openai":
        provider = "google"
        model = _model(COST_MODEL_ENV, DEFAULT_COST_MODEL)
    else:
        provider = "openai"
        model = _model(CAPABILITY_MODEL_ENV, DEFAULT_CAPABILITY_MODEL)
    return {
        "agent": decision["agent"],
        "provider": provider,
        "model": model,
        "dimension": "fallback",
        "reason": (
            f"The {decision['provider']} call failed ({error_name}), "
            f"so this step retries once on {provider}."
        ),
        "kind": decision.get("kind"),
    }


def last_token_usage() -> dict:
    tokens = _last_tokens.get()
    if not tokens:
        return {"input_tokens": 0, "output_tokens": 0}
    return {"input_tokens": tokens[0], "output_tokens": tokens[1]}


def _remember_tokens(input_tokens: int, output_tokens: int) -> None:
    _last_tokens.set((int(input_tokens or 0), int(output_tokens or 0)))


def _usage_openai(response) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    return int(getattr(usage, "input_tokens", 0) or 0), int(getattr(usage, "output_tokens", 0) or 0)


def _usage_google(response) -> tuple[int, int]:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return 0, 0
    prompt = int(getattr(meta, "prompt_token_count", 0) or 0)
    answer = int(getattr(meta, "candidates_token_count", 0) or 0)
    thoughts = int(getattr(meta, "thoughts_token_count", 0) or 0)
    return prompt, answer + thoughts


def complete(decision: dict, prompt: str, needs_tools: bool = False) -> str:
    """Call the selected model. GPT uses the Responses API, which is required for tools."""
    if decision["provider"] == "openai":
        client = OpenAI(timeout=90)
        kwargs = {
            "model": decision["model"],
            "input": prompt,
            "reasoning": {"effort": "low"},
            "max_output_tokens": 512,
        }
        if needs_tools:
            kwargs["tools"] = decision.get("tools") or []
        response = client.responses.create(**kwargs)
        text = (response.output_text or "").strip()
        _remember_tokens(*_usage_openai(response))
    elif decision["provider"] == "google":
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        response = client.models.generate_content(
            model=decision["model"],
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                max_output_tokens=512,
            ),
        )
        text = (response.text or "").strip()
        _remember_tokens(*_usage_google(response))
    else:
        raise ValueError(f"unknown provider {decision['provider']}")
    if not text:
        raise RuntimeError(f"{decision['provider']} returned an empty answer")
    return text


def _iter_deltas(decision: dict, prompt: str, needs_tools: bool):
    if decision["provider"] == "openai":
        client = OpenAI(timeout=90)
        kwargs = {
            "model": decision["model"],
            "input": prompt,
            "reasoning": {"effort": "low"},
            "max_output_tokens": 512,
        }
        if needs_tools:
            kwargs["tools"] = decision.get("tools") or []
        with client.responses.stream(**kwargs) as stream:
            for event in stream:
                if getattr(event, "type", "") == "response.output_text.delta" and event.delta:
                    yield event.delta
            _remember_tokens(*_usage_openai(stream.get_final_response()))
        return
    if decision["provider"] == "google":
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        last = None
        for chunk in client.models.generate_content_stream(
            model=decision["model"],
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                max_output_tokens=512,
            ),
        ):
            last = chunk
            text = chunk.text or ""
            if text:
                yield text
        if last is not None:
            _remember_tokens(*_usage_google(last))
        return
    raise ValueError(f"unknown provider {decision['provider']}")


def stream_complete(decision: dict, prompt: str, needs_tools: bool = False) -> str:
    """Stream Summary text. Each piece is published before the full answer exists."""
    parts: list[str] = []
    for delta in _iter_deltas(decision, prompt, needs_tools):
        parts.append(delta)
        publish("token", {"text": delta})
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError(f"{decision['provider']} returned an empty answer")
    return text


def _log_route(route_log: list[dict], entry: dict) -> None:
    route_log.append(entry)
    publish(
        "route",
        {
            "agent": entry.get("agent"),
            "provider": entry.get("provider"),
            "model": entry.get("model"),
            "dimension": entry.get("dimension"),
            "reason": entry.get("reason"),
        },
    )


def run_task(
    task: dict,
    route_log: list[dict],
    *,
    fail_providers: set[str] | None = None,
    caller: Complete = complete,
) -> dict:
    """Run one step. A provider error retries once. A second error marks the step failed."""
    blocked = fail_providers or set()
    decision = choose_provider(task)
    prompt = task["prompt"]
    needs_tools = bool(task.get("needs_tools"))

    def attempt(choice: dict) -> str:
        if choice["provider"] in blocked:
            raise RuntimeError(f"forced failure for {choice['provider']}")
        _last_tokens.set(None)
        return caller(choice, prompt, needs_tools)

    def finish(choice: dict, *, fallback: bool, recovered: bool, ok: bool, started: float) -> None:
        usage = last_token_usage()
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        _log_route(
            route_log,
            {
                **choice,
                "fallback": fallback,
                "recovered": recovered,
                "ok": ok,
                "latency_ms": latency_ms,
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
            },
        )
        outcome = "The call failed." if not ok else "The call succeeded."
        retry = " This is the retry on the other provider." if fallback else ""
        trace_event(
            choice.get("agent") or "model",
            "model",
            (
                f"{choice.get('provider')} {choice.get('model')} handled the {choice.get('kind') or 'step'} "
                f"({choice.get('dimension')}) in {latency_ms} ms. {choice.get('reason')}{retry} {outcome}"
            ),
        )

    started = time.perf_counter()
    try:
        text = attempt(decision)
    except Exception as first_error:
        finish(decision, fallback=False, recovered=False, ok=False, started=started)
        fallback = alternate_provider(decision, type(first_error).__name__)
        started = time.perf_counter()
        try:
            text = attempt(fallback)
        except Exception:
            finish(fallback, fallback=True, recovered=False, ok=False, started=started)
            return {"ok": False, "text": "", "decision": fallback, "recovered": False}
        finish(fallback, fallback=True, recovered=True, ok=True, started=started)
        return {"ok": True, "text": text, "decision": fallback, "recovered": True}

    finish(decision, fallback=False, recovered=False, ok=True, started=started)
    return {"ok": True, "text": text, "decision": decision, "recovered": False}
