"""Phase 4 routing check. Calls both providers and saves eval/route_log.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.routing import choose_provider, run_task

STARTERS = [
    {
        "id": "pep8-lookup",
        "agent": "research",
        "complexity": "low",
        "kind": "lookup",
        "question": "What does PEP 8 say about putting imports on separate lines?",
    },
    {
        "id": "final-count",
        "agent": "data",
        "complexity": "low",
        "kind": "lookup",
        "question": "A table of PEPs is available. In one sentence, what would a count of status Final tell a reader?",
    },
    {
        "id": "code-explain",
        "agent": "code",
        "complexity": "high",
        "kind": "code",
        "question": "Explain format_pep_reference in pep_tools/references.py in one sentence.",
    },
    {
        "id": "after-snapshot",
        "agent": "research",
        "complexity": "low",
        "kind": "lookup",
        "question": "Where would a reader look for PEPs accepted after a fixed documentation snapshot?",
    },
    {
        "id": "summary",
        "agent": "summary",
        "complexity": "high",
        "kind": "summary",
        "question": "Write one sentence that could summarize a PEP 8 import rule together with a count of Process PEPs.",
    },
]


def task_from(spec: dict) -> dict:
    return {
        "agent": spec["agent"],
        "complexity": spec["complexity"],
        "kind": spec["kind"],
        "prompt": f"Answer in one sentence.\n\n{spec['question']}",
    }


def main() -> None:
    route_log: list[dict] = []
    session = []
    for spec in STARTERS:
        decision = choose_provider(task_from(spec))
        result = run_task(task_from(spec), route_log)
        if not result["ok"] or not result["text"]:
            raise SystemExit(f"{spec['id']} did not return an answer")
        session.append(
            {
                "id": spec["id"],
                "question": spec["question"],
                "provider": result["decision"]["provider"],
                "model": result["decision"]["model"],
                "dimension": result["decision"]["dimension"],
                "reason": result["decision"]["reason"],
                "answer": result["text"][:400],
            }
        )
        print(f"{spec['id']}: {decision['provider']} ({decision['dimension']}) {result['text'][:160]}")

    providers = {item["provider"] for item in session}
    if providers != {"google", "openai"}:
        raise SystemExit(f"a normal session must use both providers, got {providers}")
    for entry in route_log:
        if not entry.get("reason") or not entry.get("dimension"):
            raise SystemExit(f"route entry is missing a readable reason: {entry}")

    forced_log: list[dict] = []
    forced = run_task(task_from(STARTERS[2]), forced_log, fail_providers={"openai"})
    if not forced["ok"] or forced["decision"]["provider"] != "google":
        raise SystemExit(f"fallback did not recover on Gemini: {forced_log}")
    if not any(entry.get("fallback") and entry.get("recovered") for entry in forced_log):
        raise SystemExit(f"fallback log missing recovered entry: {forced_log}")
    print(f"forced-gpt-failure: recovered via {forced['decision']['provider']} {forced['text'][:160]}")

    failed_log: list[dict] = []
    failed = run_task(task_from(STARTERS[0]), failed_log, fail_providers={"google", "openai"})
    if failed["ok"] or any(entry.get("recovered") for entry in failed_log):
        raise SystemExit("a double failure should mark the step failed and continue")
    print("double-failure: step marked failed")

    payload = {"session": session, "route_log": route_log, "forced_fallback": forced_log}
    destination = ROOT / "eval" / "route_log.json"
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {destination}")


if __name__ == "__main__":
    main()
