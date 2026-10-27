"""Ask 100 questions that are not in the first 50, against the live service.

Expected strings come from data/peps.sqlite, code_bundle/pep_tools, and
passages in the Python docs and PEPs. Results land in eval/scenario_runs_100.json.
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path

from scenario_check import SCENARIOS, ask, judge

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "scenario_runs_100.json"

SCENARIOS_100 = [
    {"id": "pep7-title", "q": "What is the title of PEP 7?", "all": ["style guide for c code"]},
    {"id": "pep4-title", "q": "What is the title of PEP 4?", "all": ["deprecation of standard modules"]},
    {"id": "pep4-author", "q": "Who is listed first among the authors of PEP 4?", "all": ["brett cannon"]},
    {"id": "pep11-title", "q": "What is the title of PEP 11?", "all": ["cpython platform support"]},
    {"id": "pep13-title", "q": "What is the title of PEP 13?", "all": ["python language governance"]},
    {"id": "pep13-type", "q": "What are the status and type of PEP 13 in the table?", "all": ["active", "process"]},
    {"id": "pep5-status", "q": "What is the status of PEP 5 in the table?", "all": ["superseded"]},
    {"id": "pep234-meta", "q": "What is the title of PEP 234, and which Python version does the table record?", "all": ["iterators", "final"], "numbers": ["2.1"]},
    {"id": "pep249-meta", "q": "What is the title and type of PEP 249?", "all": ["database api", "informational"]},
    {"id": "pep255-meta", "q": "What is the title of PEP 255, and which Python version does the table record?", "all": ["simple generators"], "numbers": ["2.2"]},
    {"id": "pep263-meta", "q": "What is PEP 263 about, and which Python version does the table record?", "all": ["encodings"], "numbers": ["2.3"]},
    {"id": "pep285-author", "q": "Who authored PEP 285, and what is its title?", "all": ["guido van rossum", "bool"]},
    {"id": "pep315-status", "q": "What is the status of PEP 315 in the table?", "all": ["rejected"]},
    {"id": "pep328-title", "q": "What is the title of PEP 328?", "all": ["absolute/relative"]},
    {"id": "pep343-meta", "q": "What is the title of PEP 343, and which Python version does the table record?", "all": ["with"], "numbers": ["2.5"]},
    {"id": "pep362-meta", "q": "What is the title of PEP 362, and which Python version does the table record?", "all": ["function signature"], "numbers": ["3.3"]},
    {"id": "pep380-meta", "q": "What is the title of PEP 380, and which Python version does the table record?", "all": ["subgenerator"], "numbers": ["3.3"]},
    {"id": "pep393-meta", "q": "What is the title of PEP 393, and which Python version does the table record?", "all": ["flexible string"], "numbers": ["3.3"]},
    {"id": "pep420-meta", "q": "What is the title of PEP 420, and which Python version does the table record?", "all": ["namespace packages"], "numbers": ["3.3"]},
    {"id": "pep426-status", "q": "What is the status of PEP 426 in the table?", "all": ["withdrawn"]},
    {"id": "pep428-meta", "q": "What is the title of PEP 428, and which Python version does the table record?", "all": ["pathlib"], "numbers": ["3.4"]},
    {"id": "pep435-meta", "q": "What is the title of PEP 435, and which Python version does the table record?", "all": ["enum"], "numbers": ["3.4"]},
    {"id": "pep443-meta", "q": "What is the title of PEP 443, and which Python version does the table record?", "all": ["single-dispatch"], "numbers": ["3.4"]},
    {"id": "pep448-meta", "q": "What is the title of PEP 448, and which Python version does the table record?", "all": ["unpacking"], "numbers": ["3.5"]},
    {"id": "pep465-meta", "q": "What is the title of PEP 465, and which Python version does the table record?", "all": ["matrix multiplication"], "numbers": ["3.5"]},
    {"id": "pep492-meta", "q": "What is the title of PEP 492, and which Python version does the table record?", "all": ["async and await"], "numbers": ["3.5"]},
    {"id": "pep498-meta", "q": "What is the title of PEP 498, and which Python version does the table record?", "all": ["literal string interpolation"], "numbers": ["3.6"]},
    {"id": "pep517-title", "q": "What is the title of PEP 517, and what is its status?", "all": ["build-system", "final"]},
    {"id": "pep525-meta", "q": "What is the title of PEP 525, and which Python version does the table record?", "all": ["asynchronous generators"], "numbers": ["3.6"]},
    {"id": "pep526-meta", "q": "What is the title of PEP 526, and which Python version does the table record?", "all": ["variable annotations"], "numbers": ["3.6"]},
    {"id": "pep544-meta", "q": "What is the title of PEP 544, and which Python version does the table record?", "all": ["protocols"], "numbers": ["3.8"]},
    {"id": "pep557-meta", "q": "What is the title of PEP 557, and which Python version does the table record?", "all": ["data classes"], "numbers": ["3.7"]},
    {"id": "pep563-status", "q": "What is the title and status of PEP 563?", "all": ["postponed evaluation of annotations", "superseded"]},
    {"id": "pep584-meta", "q": "What is the title of PEP 584, and which Python version does the table record?", "all": ["union operators"], "numbers": ["3.9"]},
    {"id": "pep585-meta", "q": "What is the title of PEP 585, and which Python version does the table record?", "all": ["generics"], "numbers": ["3.9"]},
    {"id": "pep589-meta", "q": "What is the title of PEP 589, and which Python version does the table record?", "all": ["typeddict"], "numbers": ["3.8"]},
    {"id": "pep604-meta", "q": "What Python version does the table record for PEP 604, and what is its status?", "all": ["final"], "numbers": ["3.10"]},
    {"id": "pep617-meta", "q": "What is the title of PEP 617, and which Python version does the table record?", "all": ["peg parser"], "numbers": ["3.9"]},
    {"id": "pep634-meta", "q": "What is the title of PEP 634, and which Python version does the table record?", "all": ["structural pattern matching", "specification"], "numbers": ["3.10"]},
    {"id": "pep649-meta", "q": "What is the title of PEP 649, and which Python version does the table record?", "all": ["deferred evaluation"], "numbers": ["3.14"]},
    {"id": "pep657-meta", "q": "What is the title of PEP 657, and which Python version does the table record?", "all": ["tracebacks"], "numbers": ["3.11"]},
    {"id": "pep679-status", "q": "What is the status of PEP 679 in the table?", "all": ["rejected"]},
    {"id": "pep695-meta", "q": "What is the title of PEP 695, and which Python version does the table record?", "all": ["type parameter syntax"], "numbers": ["3.12"]},
    {"id": "pep701-meta", "q": "What is the title of PEP 701, and which Python version does the table record?", "all": ["f-strings"], "numbers": ["3.12"]},
    {"id": "pep709-meta", "q": "What is the title of PEP 709, and which Python version does the table record?", "all": ["inlined comprehensions"], "numbers": ["3.12"]},
    {"id": "pep723-title", "q": "What is the title and status of PEP 723?", "all": ["inline script metadata", "final"]},
    {"id": "pep401-status", "q": "What is the title and status of PEP 401?", "all": ["bdfl retirement", "april fool"]},
    {"id": "pep801-meta", "q": "What is the title, status, and author of PEP 801?", "all": ["reserved", "active", "barry warsaw"]},
    {"id": "no-version-count", "q": "How many PEPs have no Python-Version recorded?", "numbers": ["217"]},
    {"id": "has-version-count", "q": "How many PEPs have a Python-Version value recorded?", "numbers": ["528"]},
    {"id": "final-informational", "q": "How many PEPs are both status Final and type Informational?", "numbers": ["51"]},
    {"id": "final-standards", "q": "How many PEPs are both status Final and type Standards Track?", "numbers": ["308"]},
    {"id": "active-process", "q": "How many PEPs are both status Active and type Process?", "numbers": ["19"]},
    {"id": "accepted-standards", "q": "How many PEPs are both status Accepted and type Standards Track?", "numbers": ["9"]},
    {"id": "rejected-process", "q": "How many PEPs are both status Rejected and type Process?", "numbers": ["3"]},
    {"id": "withdrawn-process", "q": "How many PEPs are both status Withdrawn and type Process?", "numbers": ["9"]},
    {"id": "superseded-informational", "q": "How many PEPs are both status Superseded and type Informational?", "numbers": ["6"]},
    {"id": "barry-count", "q": "How many PEP rows list Barry Warsaw as an author?", "numbers": ["46"]},
    {"id": "tim-count", "q": "How many PEP rows list Tim Peters as an author?", "numbers": ["11"]},
    {"id": "brett-count", "q": "How many PEP rows list Brett Cannon as an author?", "numbers": ["35"]},
    {"id": "alyssa-count", "q": "How many PEP rows list Alyssa Coghlan as an author?", "numbers": ["53"]},
    {"id": "raymond-count", "q": "How many PEP rows list Raymond Hettinger as an author?", "numbers": ["14"]},
    {"id": "goodger-count", "q": "How many PEP rows list David Goodger as an author?", "numbers": ["6"]},
    {"id": "shannon-count", "q": "How many PEP rows list Mark Shannon as an author?", "numbers": ["14"]},
    {"id": "langa-count", "q": "How many PEP rows list Langa as an author?", "numbers": ["15"]},
    {"id": "both-guido-barry", "q": "How many PEP rows list both Guido van Rossum and Barry Warsaw as authors?", "numbers": ["5"]},
    {"id": "py39-count", "q": "How many PEPs list Python-Version 3.9?", "numbers": ["15"]},
    {"id": "py310-count", "q": "How many PEPs list Python-Version 3.10?", "numbers": ["21"]},
    {"id": "py311-count", "q": "How many PEPs list Python-Version 3.11?", "numbers": ["17"]},
    {"id": "py312-count", "q": "How many PEPs list Python-Version 3.12?", "numbers": ["25"]},
    {"id": "py314-count", "q": "How many PEPs list Python-Version 3.14?", "numbers": ["25"]},
    {"id": "py315-count", "q": "How many PEPs list Python-Version 3.15?", "numbers": ["32"]},
    {"id": "py316-count", "q": "How many PEPs list Python-Version 3.16?", "numbers": ["26"]},
    {"id": "created-2025", "q": "How many PEP rows have a Created date in 2025?", "numbers": ["45"]},
    {"id": "created-2024", "q": "How many PEP rows have a Created date in 2024?", "numbers": ["34"]},
    {"id": "created-2000", "q": "How many PEP rows have a Created date in 2000?", "numbers": ["40"]},
    {"id": "url-20", "q": "What URL does pep_url(20) return in code_bundle/pep_tools/references.py?", "all": ["https://peps.python.org/pep-0020/"]},
    {"id": "url-257", "q": "What URL does pep_url(257) return in code_bundle/pep_tools/references.py?", "all": ["https://peps.python.org/pep-0257/"]},
    {"id": "url-0", "q": "What URL does pep_url(0) return in code_bundle/pep_tools/references.py?", "all": ["https://peps.python.org/pep-0000/"]},
    {"id": "url-100", "q": "What URL does pep_url(100) return in code_bundle/pep_tools/references.py?", "all": ["https://peps.python.org/pep-0100/"]},
    {"id": "url-10000", "q": "What URL does pep_url(10000) return in code_bundle/pep_tools/references.py?", "all": ["https://peps.python.org/pep-10000/"]},
    {"id": "format-257", "q": "What string does format_pep_reference(257, 'Docstring Conventions') return?", "all": ["pep 257", "docstring conventions", "pep-0257"]},
    {"id": "format-collapse", "q": "What string does format_pep_reference return for number 20 and title '  The   Zen of Python  ' after it cleans whitespace?", "all": ["pep 20: the zen of python", "pep-0020"]},
    {"id": "group-os", "q": "What does import_group('os') return in code_bundle/pep_tools/style.py?", "all": ["stdlib"]},
    {"id": "group-ospath", "q": "What does import_group('os.path') return in code_bundle/pep_tools/style.py?", "all": ["stdlib"]},
    {"id": "group-requests", "q": "What does import_group('requests') return in code_bundle/pep_tools/style.py?", "any": ["returns other", "return other", "'other'", '"other"', "labeled other"]},
    {"id": "imports-separate-true", "q": "What does imports_are_on_separate_lines return for source that contains import os on one line and import sys on the next line?", "any": ["true", "yes"]},
    {"id": "imports-json-false", "q": "What does imports_are_on_separate_lines return for the source import json, pathlib?", "any": ["false", "not on separate"]},
    {"id": "header-hello-world", "q": "In code_bundle, parse_pep_header is given the text Title: Hello followed by a newline and two spaces then World. What is the Title value?", "all": ["hello world"]},
    {"id": "negative-message", "q": "What error message does pep_url raise when the PEP number is negative?", "all": ["must be zero or greater"]},
    {"id": "zen-beautiful", "q": "Quote the Zen of Python line that begins with Beautiful.", "all": ["beautiful is better than ugly"]},
    {"id": "zen-simple", "q": "Quote the Zen of Python line that begins with Simple.", "all": ["simple is better than complex"]},
    {"id": "zen-flat", "q": "Quote the Zen of Python line that begins with Flat.", "all": ["flat is better than nested"]},
    {"id": "zen-sparse", "q": "Quote the Zen of Python line that begins with Sparse.", "all": ["sparse is better than dense"]},
    {"id": "zen-errors", "q": "Quote the Zen of Python line about errors passing silently.", "all": ["errors should never pass silently"]},
    {"id": "zen-ambiguity", "q": "Quote the Zen of Python line about ambiguity.", "all": ["refuse the temptation to guess"]},
    {"id": "zen-namespaces", "q": "Quote the Zen of Python line about namespaces.", "all": ["namespaces are one honking great idea"]},
    {"id": "pep8-79", "q": "What maximum line length does PEP 8 recommend, in characters?", "numbers": ["79"]},
    {"id": "pep257-quotes", "q": "According to PEP 257, where do the closing quotes of a one-line docstring go?", "all": ["same line"]},
    {"id": "glossary-generator", "q": "What does the Python glossary say a generator is?", "any": ["returns an iterator", "returns a iterator", "function which returns", "yield"]},
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    old_ids = {item["id"] for item in SCENARIOS}
    old_questions = {item["q"] for item in SCENARIOS}
    ids = [item["id"] for item in SCENARIOS_100]
    if len(SCENARIOS_100) != 100 or len(set(ids)) != 100:
        raise SystemExit(f"expected 100 unique scenarios, found {len(ids)}")
    overlap = old_ids & set(ids)
    same_question = [item["id"] for item in SCENARIOS_100 if item["q"] in old_questions]
    if overlap or same_question:
        raise SystemExit(f"overlap with the first 50: {overlap or same_question}")
    results = []
    if OUT.exists():
        results = json.loads(OUT.read_text(encoding="utf-8")).get("results") or []
    done = {item["id"] for item in results}
    for index, spec in enumerate(SCENARIOS_100, start=1):
        if spec["id"] in done:
            continue
        print(f"[{index}/100] {spec['id']}", flush=True)
        reply = _ask(spec["q"])
        if not reply["answer"]:
            reply = _ask(spec["q"])
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


def _ask(question: str) -> dict:
    try:
        return ask(question)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"answer": "", "routes": [], "errors": [type(exc).__name__], "ms": 0}


if __name__ == "__main__":
    main()
