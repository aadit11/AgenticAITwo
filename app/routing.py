"""Provider selection and one-retry fallback.

The plan step sets complexity to low or high. This module reads that field.
It does not inspect the user question.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from google import genai
from google.genai import types
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

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
    else:
        raise ValueError(f"unknown provider {decision['provider']}")
    if not text:
        raise RuntimeError(f"{decision['provider']} returned an empty answer")
    return text


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
        return caller(choice, prompt, needs_tools)

    try:
        text = attempt(decision)
    except Exception as first_error:
        fallback = alternate_provider(decision, type(first_error).__name__)
        route_log.append({**decision, "fallback": False, "recovered": False, "ok": False})
        try:
            text = attempt(fallback)
        except Exception:
            route_log.append({**fallback, "fallback": True, "recovered": False, "ok": False})
            return {"ok": False, "text": "", "decision": fallback, "recovered": False}
        route_log.append({**fallback, "fallback": True, "recovered": True, "ok": True})
        return {"ok": True, "text": text, "decision": fallback, "recovered": True}

    route_log.append({**decision, "fallback": False, "recovered": False, "ok": True})
    return {"ok": True, "text": text, "decision": decision, "recovered": False}
