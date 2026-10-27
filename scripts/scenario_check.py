"""Ask 50 questions with known answers and record which replies contain them."""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://multi-agent-rag-749179608015.us-west1.run.app/api/chat"
OUT = ROOT / "eval" / "scenario_runs.json"

# all: every string must appear. any: at least one must appear.
# numbers: digit sequences matched on a word boundary.
SCENARIOS = [
    {"id": "final-count", "q": "How many PEPs in the table have status Final?", "numbers": ["375"]},
    {"id": "rejected-count", "q": "How many PEPs have status Rejected?", "numbers": ["131"]},
    {"id": "withdrawn-count", "q": "How many PEPs have status Withdrawn?", "numbers": ["74"]},
    {"id": "draft-count", "q": "How many PEPs have status Draft?", "numbers": ["55"]},
    {"id": "active-count", "q": "How many PEPs have status Active?", "numbers": ["37"]},
    {"id": "deferred-count", "q": "How many PEPs have status Deferred?", "numbers": ["35"]},
    {"id": "superseded-count", "q": "How many PEPs have status Superseded?", "numbers": ["25"]},
    {"id": "accepted-count", "q": "How many PEPs have status Accepted?", "numbers": ["11"]},
    {"id": "process-count", "q": "How many PEPs have type Process?", "numbers": ["53"]},
    {"id": "standards-count", "q": "How many PEPs have type Standards Track?", "numbers": ["587"]},
    {"id": "informational-count", "q": "How many PEPs have type Informational?", "numbers": ["105"]},
    {"id": "total-count", "q": "How many PEPs are in the table?", "numbers": ["745"]},
    {"id": "final-process", "q": "How many PEPs are both status Final and type Process?", "numbers": ["16"]},
    {"id": "py313-count", "q": "How many PEPs list Python-Version 3.13?", "numbers": ["18"]},
    {"id": "guido-count", "q": "How many PEP rows list Guido van Rossum as an author?", "numbers": ["50"]},
    {"id": "pep8-status", "q": "What is the status of PEP 8 in the table?", "all": ["active"]},
    {"id": "pep8-type", "q": "What is the type of PEP 8 in the table?", "all": ["process"]},
    {"id": "pep8-title", "q": "What is the title of PEP 8?", "all": ["style guide"]},
    {"id": "pep20-title", "q": "What is the title of PEP 20?", "all": ["zen of python"]},
    {"id": "pep20-author", "q": "Who authored PEP 20, according to the table?", "all": ["tim peters"]},
    {"id": "pep257-title", "q": "What is the title of PEP 257?", "all": ["docstring"]},
    {"id": "pep484-meta", "q": "What are the status and Python version of PEP 484?", "all": ["final"], "numbers": ["3.5"]},
    {"id": "pep572-meta", "q": "What is the title of PEP 572, and which Python version does the table record?", "all": ["assignment expressions"], "numbers": ["3.8"]},
    {"id": "pep703-meta", "q": "What is PEP 703 about, and what Python version and status does the table give it?", "all": ["gil", "final"], "any": ["optional", "3.13"]},
    {"id": "pep318-meta", "q": "What is the status of PEP 318 and which Python version does the table record?", "all": ["final"], "numbers": ["2.4"]},
    {"id": "pep314-status", "q": "What is the status of PEP 314 in the table?", "all": ["superseded"]},
    {"id": "pep1-title", "q": "What is the title and status of PEP 1?", "all": ["purpose and guidelines", "active"]},
    {"id": "max-number", "q": "What is the highest PEP number in the table?", "numbers": ["8107"]},
    {"id": "pep8-imports", "q": "What does PEP 8 say about imports?", "all": ["separate lines"], "any": ["import os", "import sys"]},
    {"id": "pep8-blank", "q": "What does PEP 8 say about blank lines around functions and methods?", "all": ["two", "one"]},
    {"id": "pep8-indent", "q": "How many spaces does PEP 8 use per indentation level?", "any": ["4 spaces", "four spaces"]},
    {"id": "pep20-readability", "q": "Which line of the Zen of Python says that readability counts?", "all": ["readability counts"]},
    {"id": "pep-acronym", "q": "What does PEP stand for, according to PEP 1?", "all": ["python enhancement proposal"]},
    {"id": "decorator", "q": "What does the Python glossary say a decorator is?", "any": ["returning another function", "wraps", "function that wraps"]},
    {"id": "len-builtin", "q": "What does the len built-in return?", "any": ["number of items", "length", "__len__"]},
    {"id": "pep257-topic", "q": "What conventions does PEP 257 describe?", "all": ["docstring"]},
    {"id": "zen-explicit", "q": "Quote the Zen of Python line that prefers explicit to implicit.", "all": ["explicit is better than implicit"]},
    {"id": "pep8-spaces", "q": "Does PEP 8 prefer spaces or tabs for indentation?", "all": ["spaces"]},
    {"id": "format-ref", "q": "What string does format_pep_reference(8, 'Style Guide') return?", "all": ["pep 8", "style guide", "pep-0008"]},
    {"id": "pep-url", "q": "What URL does pep_url(8) return in code_bundle/pep_tools/references.py?", "all": ["https://peps.python.org/pep-0008/"]},
    {"id": "import-false", "q": "What does imports_are_on_separate_lines return for the source import os, sys?", "any": ["false", "not on separate", "wrong"]},
    {"id": "from-import-ok", "q": "Does imports_are_on_separate_lines allow from module import a, b?", "any": ["allow", "yes", "true", "acceptable", "okay", "permitted"]},
    {"id": "header-join", "q": "How does parse_pep_header treat a continuation line in a PEP header?", "any": ["join", "joined", "continuation", "space"]},
    {"id": "negative-url", "q": "What does pep_url do when the PEP number is negative?", "all": ["valueerror"]},
    {"id": "imports-and-process", "q": "In one paragraph, give one PEP 8 import rule and the number of Process PEPs.", "all": ["separate"], "numbers": ["53"]},
    {"id": "pep8-authors", "q": "Who are the authors of PEP 8 in the table?", "all": ["guido", "barry", "alyssa"]},
    {"id": "after-snapshot", "q": "What PEPs were accepted after the corpus snapshot date?", "any": ["does not", "do not", "cannot", "can't", "not identify", "not establish", "no information", "does not contain"]},
    {"id": "world-cup", "q": "Who won the 2026 FIFA World Cup?", "min_chars": 40},
    {"id": "paris", "q": "What is the capital of France?", "any": ["paris", "does not", "do not", "corpus"]},
    {"id": "provisional", "q": "How many PEPs have status Provisional?", "numbers": ["1"]},
]


def ask(question: str) -> dict:
    payload = json.dumps({"query": question, "history": []}).encode("utf-8")
    request = urllib.request.Request(
        URL,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    started = time.perf_counter()
    answer: list[str] = []
    routes: list[str] = []
    errors: list[str] = []
    with urllib.request.urlopen(request, timeout=300) as response:
        buffer = ""
        while True:
            chunk = response.read(512)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n\n" in buffer:
                frame, buffer = buffer.split("\n\n", 1)
                event, data = "message", ""
                for line in frame.splitlines():
                    if line.startswith("event:"):
                        event = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        data += line.split(":", 1)[1].strip()
                if not data or data == "{}":
                    if event == "done":
                        break
                    continue
                try:
                    body = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if event == "token":
                    answer.append(body.get("text") or "")
                elif event == "route":
                    routes.append(f"{body.get('agent')}:{body.get('provider')}")
                elif event == "error":
                    errors.append(body.get("message") or "error")
                elif event == "done":
                    break
            else:
                continue
            break
    return {
        "answer": "".join(answer).strip(),
        "routes": routes,
        "errors": errors,
        "ms": round((time.perf_counter() - started) * 1000, 1),
    }


def judge(spec: dict, answer: str) -> tuple[bool, str]:
    text = answer.casefold()
    if not text or "could not produce" in text or "failed before" in text or "briefing stopped" in text:
        return False, "no usable answer"
    missing = []
    for needle in spec.get("all") or []:
        if needle.casefold() not in text:
            missing.append(needle)
    if spec.get("any") and not any(needle.casefold() in text for needle in spec["any"]):
        missing.append("one of " + ", ".join(spec["any"]))
    for number in spec.get("numbers") or []:
        if not re.search(rf"(?<!\d){re.escape(number)}(?!\d)", answer):
            missing.append(number)
    if len(answer) < spec.get("min_chars", 0):
        missing.append(f"at least {spec['min_chars']} characters")
    if missing:
        return False, "missing " + "; ".join(missing)
    return True, "ok"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = []
    if OUT.exists():
        results = json.loads(OUT.read_text(encoding="utf-8")).get("results") or []
    done = {item["id"] for item in results}
    for index, spec in enumerate(SCENARIOS, start=1):
        if spec["id"] in done:
            continue
        print(f"[{index}/{len(SCENARIOS)}] {spec['id']}", flush=True)
        try:
            reply = ask(spec["q"])
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            reply = {"answer": "", "routes": [], "errors": [type(exc).__name__], "ms": 0}
        passed, reason = judge(spec, reply["answer"])
        row = {
            "id": spec["id"],
            "question": spec["q"],
            "pass": passed,
            "reason": reason,
            "ms": reply["ms"],
            "routes": reply["routes"],
            "errors": reply["errors"],
            "answer": reply["answer"],
        }
        results.append(row)
        OUT.write_text(json.dumps({"results": results}, indent=2) + "\n", encoding="utf-8")
        print(f"  {'PASS' if passed else 'FAIL'} {reason} {reply['ms']} ms", flush=True)
        print("  " + reply["answer"][:220].replace("\n", " "), flush=True)
    passed = sum(1 for item in results if item["pass"])
    print(f"\n{passed}/{len(results)} passed", flush=True)
    for item in results:
        if not item["pass"]:
            print(f"FAIL {item['id']}: {item['reason']}", flush=True)


if __name__ == "__main__":
    main()
