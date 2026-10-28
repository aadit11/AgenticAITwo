"""100 new questions. Each one checks the answer and which agents ran.

A pass requires the expected fact and this path: plan, then only the named
workers, then summary. Data and research use Google. Code and summary use OpenAI.
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path

from scenario_check import SCENARIOS, ask, judge
from scenario_check_100 import SCENARIOS_100

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "scenario_runs_path.json"
WORKERS = ("research", "data", "code")

TABLE = "Answer from the PEP table only. "
DOC = "Answer from the Python documentation or PEP text, not from the table or code bundle. "
CODE = "Answer from code_bundle/pep_tools only. "
BOTH = "Use the PEP text and the PEP table. "

SCENARIOS_PATH = [
    {"id": "p-pep2", "q": TABLE + "What is the title and status of PEP 2?", "all": ["adding new modules", "active"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep3", "q": TABLE + "What is the status of PEP 3?", "all": ["withdrawn"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep9", "q": TABLE + "What is the title and status of PEP 9?", "all": ["plaintext pep template", "withdrawn"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep12", "q": TABLE + "What is the title and status of PEP 12?", "all": ["restructuredtext", "active"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep103", "q": TABLE + "What is the status and type of PEP 103?", "all": ["withdrawn", "informational"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep208", "q": TABLE + "What is the title of PEP 208, and which Python version does the table record?", "all": ["coercion"], "numbers": ["2.1"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep210", "q": TABLE + "What is the status of PEP 210?", "all": ["rejected"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep218", "q": TABLE + "What is the title of PEP 218, and which Python version does the table record?", "all": ["set object"], "numbers": ["2.2"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep223", "q": TABLE + "What is the status of PEP 223, and which Python version does the table record?", "all": ["final"], "numbers": ["2.0"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep235", "q": TABLE + "What is the title of PEP 235?", "all": ["case-insensitive"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep237", "q": TABLE + "What is the title of PEP 237, and which Python version does the table record?", "all": ["long integers"], "numbers": ["2.2"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep238", "q": TABLE + "What is the title of PEP 238, and which Python version does the table record?", "all": ["division operator"], "numbers": ["2.2"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep241", "q": TABLE + "What is the status of PEP 241?", "all": ["superseded"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep247", "q": TABLE + "What is the title and type of PEP 247?", "all": ["cryptographic hash", "informational"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep248", "q": TABLE + "What is the title of PEP 248?", "all": ["database api specification v1.0"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep252", "q": TABLE + "What is the title of PEP 252, and which Python version does the table record?", "all": ["types look more like classes"], "numbers": ["2.2"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep261", "q": TABLE + "What is the title of PEP 261, and which Python version does the table record?", "all": ["unicode"], "numbers": ["2.2"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep267", "q": TABLE + "What is the status of PEP 267?", "all": ["deferred"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep273", "q": TABLE + "What is the title of PEP 273, and which Python version does the table record?", "all": ["zip archives"], "numbers": ["2.3"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep277", "q": TABLE + "What is the title of PEP 277, and which Python version does the table record?", "all": ["unicode file name"], "numbers": ["2.3"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep279", "q": TABLE + "What is the title of PEP 279, and which Python version does the table record?", "all": ["enumerate"], "numbers": ["2.3"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pep228", "q": TABLE + "What is the status of PEP 228?", "all": ["withdrawn"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-eric", "q": TABLE + "How many PEP rows list Eric V. Smith as an author?", "numbers": ["4"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-yury", "q": TABLE + "How many PEP rows list Yury Selivanov as an author?", "numbers": ["9"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-pablo", "q": TABLE + "How many PEP rows list Pablo Galindo as an author?", "numbers": ["15"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-antoine", "q": TABLE + "How many PEP rows list Antoine Pitrou as an author?", "numbers": ["13"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-brandt", "q": TABLE + "How many PEP rows list Brandt Bucher as an author?", "numbers": ["7"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-larry", "q": TABLE + "How many PEP rows list Larry Hastings as an author?", "numbers": ["8"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-ivan", "q": TABLE + "How many PEP rows list Ivan Levkivskyi as an author?", "numbers": ["8"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-steven", "q": TABLE + "How many PEP rows list Steven D'Aprano as an author?", "numbers": ["3"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-carl", "q": TABLE + "How many PEP rows list Carl Meyer as an author?", "numbers": ["4"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-year-2003", "q": TABLE + "How many PEP rows have a Created date in 2003?", "numbers": ["27"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-year-2006", "q": TABLE + "How many PEP rows have a Created date in 2006?", "numbers": ["23"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-year-2011", "q": TABLE + "How many PEP rows have a Created date in 2011?", "numbers": ["16"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-year-2018", "q": TABLE + "How many PEP rows have a Created date in 2018?", "numbers": ["26"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-year-2022", "q": TABLE + "How many PEP rows have a Created date in 2022?", "numbers": ["25"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-year-2026", "q": TABLE + "How many PEP rows have a Created date in 2026?", "numbers": ["29"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-withdrawn-info", "q": TABLE + "How many PEPs are both status Withdrawn and type Informational?", "numbers": ["11"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-rejected-info", "q": TABLE + "How many PEPs are both status Rejected and type Informational?", "numbers": ["12"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-superseded-process", "q": TABLE + "How many PEPs are both status Superseded and type Process?", "numbers": ["3"], "need": ["data"], "forbid": ["research", "code"]},
    {"id": "p-zen-complex", "q": DOC + "Quote the Zen of Python line that begins with Complex.", "all": ["complex is better than complicated"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-zen-special", "q": DOC + "Quote the Zen of Python line about special cases.", "all": ["special cases aren't special enough to break the rules"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-zen-practicality", "q": DOC + "Quote the Zen of Python line about practicality.", "all": ["practicality beats purity"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-zen-silenced", "q": DOC + "Quote the Zen of Python line about explicitly silenced errors.", "all": ["unless explicitly silenced"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-zen-now", "q": DOC + "Quote the Zen of Python line that begins with Now.", "all": ["now is better than never"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-zen-never", "q": DOC + "Quote the Zen of Python line that says never is often better than right now.", "all": ["never is often better"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-zen-hard", "q": DOC + "Quote the Zen of Python line about an implementation that is hard to explain.", "all": ["hard to explain", "bad idea"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-zen-easy", "q": DOC + "Quote the Zen of Python line about an implementation that is easy to explain.", "all": ["easy to explain"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-zen-one-way", "q": DOC + "Quote the Zen of Python line about one obvious way to do it.", "all": ["obvious way"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-pep8-72", "q": DOC + "What line length does PEP 8 recommend for comments and docstrings?", "numbers": ["72"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-pep8-trailing", "q": DOC + "What does PEP 8 say about trailing whitespace?", "all": ["trailing whitespace"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-pep8-groups", "q": DOC + "In what order does PEP 8 group imports?", "all": ["standard library"], "any": ["third party", "third-party"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-pep8-mix", "q": DOC + "Does PEP 8 allow mixing tabs and spaces for indentation?", "any": ["disallow", "not allowed", "never mix", "do not mix", "should not"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-pep257-phrase", "q": DOC + "What does PEP 257 say a one-line docstring should be, a phrase or a sentence fragment?", "any": ["phrase", "period"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-glossary-list", "q": DOC + "What does the Python glossary say a list is?", "any": ["mutable", "sequence"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-glossary-tuple", "q": DOC + "What does the Python glossary say a tuple is?", "any": ["immutable", "sequence"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-glossary-dict", "q": DOC + "What does the Python glossary say a dictionary is?", "any": ["mapping", "key"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-pep20-counts", "q": DOC + "Quote the Zen of Python line that says readability counts.", "all": ["readability counts"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-pep8-operators", "q": DOC + "Does PEP 8 put spaces around the assignment operator in a keyword argument?", "any": ["do not", "don't", "no space", "without spaces", "not use spaces"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-pep1-author", "q": DOC + "According to PEP 1, what does the abbreviation PEP stand for?", "all": ["python enhancement proposal"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-pep8-blank-top", "q": DOC + "How many blank lines does PEP 8 put around top-level function and class definitions?", "any": ["two", "2"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-zen-ugly", "q": DOC + "Quote the first line of the Zen of Python.", "all": ["beautiful is better than ugly"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-zen-nested", "q": DOC + "Quote the Zen of Python line that begins with Flat.", "all": ["flat is better than nested"], "need": ["research"], "forbid": ["data", "code"]},
    {"id": "p-url-2", "q": CODE + "What URL does pep_url(2) return?", "all": ["https://peps.python.org/pep-0002/"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-url-12", "q": CODE + "What URL does pep_url(12) return?", "all": ["https://peps.python.org/pep-0012/"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-url-279", "q": CODE + "What URL does pep_url(279) return?", "all": ["https://peps.python.org/pep-0279/"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-url-484", "q": CODE + "What URL does pep_url(484) return?", "all": ["https://peps.python.org/pep-0484/"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-url-703", "q": CODE + "What URL does pep_url(703) return?", "all": ["https://peps.python.org/pep-0703/"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-url-8107", "q": CODE + "What URL does pep_url(8107) return?", "all": ["https://peps.python.org/pep-8107/"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-format-2", "q": CODE + "What string does format_pep_reference(2, 'Procedure for Adding New Modules') return?", "all": ["pep 2", "procedure for adding new modules", "pep-0002"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-format-279", "q": CODE + "What string does format_pep_reference(279, 'The enumerate() built-in function') return?", "all": ["pep 279", "enumerate", "pep-0279"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-format-spaces", "q": CODE + "What string does format_pep_reference return for number 435 and title '  Enum   Type  ' after it cleans whitespace?", "all": ["pep 435: enum type", "pep-0435"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-url-401", "q": CODE + "What URL does pep_url(401) return?", "all": ["https://peps.python.org/pep-0401/"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-group-re", "q": CODE + "What does import_group('re') return?", "all": ["stdlib"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-group-json", "q": CODE + "What does import_group('json') return?", "all": ["stdlib"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-group-typing", "q": CODE + "What does import_group('typing') return?", "all": ["stdlib"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-group-sqlite", "q": CODE + "What does import_group('sqlite3') return?", "all": ["stdlib"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-group-dataclasses", "q": CODE + "What does import_group('dataclasses') return?", "all": ["stdlib"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-group-itertools", "q": CODE + "What does import_group('itertools') return?", "all": ["stdlib"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-group-collections", "q": CODE + "What does import_group('collections.abc') return?", "all": ["stdlib"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-group-numpy", "q": CODE + "What does import_group('numpy') return?", "any": ["returns other", "return other", "'other'", '"other"'], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-group-pandas", "q": CODE + "What does import_group('pandas.core') return?", "any": ["returns other", "return other", "'other'", '"other"'], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-import-json-os", "q": CODE + "What does imports_are_on_separate_lines return for the source import json, os?", "any": ["false", "not on separate"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-from-os", "q": CODE + "Does imports_are_on_separate_lines allow the source from os import path, getcwd?", "any": ["allow", "yes", "true", "does not reject", "not rejected"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-header-ada", "q": CODE + "parse_pep_header is given Author: Ada followed by a newline, two spaces, and Lovelace. What is the Author value?", "all": ["ada lovelace"], "need": ["code"], "forbid": ["research", "data"]},
    {"id": "p-mix-draft", "q": BOTH + "Quote the Zen line that says readability counts, and say how many PEPs have status Draft.", "all": ["readability counts"], "numbers": ["55"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-withdrawn", "q": BOTH + "Give one PEP 8 rule that imports belong on separate lines, and the number of PEPs with status Withdrawn.", "all": ["separate"], "numbers": ["74"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-active", "q": BOTH + "Quote the Zen line that begins with Beautiful, and say how many PEPs have status Active.", "all": ["beautiful is better than ugly"], "numbers": ["37"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-final", "q": BOTH + "Quote the Zen line that prefers explicit to implicit, and say how many PEPs have status Final.", "all": ["explicit is better than implicit"], "numbers": ["375"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-rejected", "q": BOTH + "Quote the Zen line that begins with Simple, and say how many PEPs have status Rejected.", "all": ["simple is better than complex"], "numbers": ["131"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-process", "q": BOTH + "Quote the Zen line that begins with Flat, and say how many PEPs have type Process.", "all": ["flat is better than nested"], "numbers": ["53"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-info", "q": BOTH + "Quote the Zen line about errors passing silently, and say how many PEPs have type Informational.", "all": ["errors should never pass silently"], "numbers": ["105"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-standards", "q": BOTH + "Quote the Zen line about namespaces, and say how many PEPs have type Standards Track.", "all": ["namespaces are one honking great idea"], "numbers": ["587"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-guido", "q": BOTH + "What maximum line length does PEP 8 recommend for code, and how many PEP rows list Guido van Rossum as an author?", "numbers": ["79", "50"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-provisional", "q": BOTH + "Where do the closing quotes of a one-line PEP 257 docstring go, and how many PEPs have status Provisional?", "all": ["same line"], "numbers": ["1"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-deferred", "q": BOTH + "Quote the Zen line that begins with Sparse, and say how many PEPs have status Deferred.", "all": ["sparse is better than dense"], "numbers": ["35"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-superseded", "q": BOTH + "Quote the Zen line about practicality, and say how many PEPs have status Superseded.", "all": ["practicality beats purity"], "numbers": ["25"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-accepted", "q": BOTH + "Quote the Zen line that begins with Now, and say how many PEPs have status Accepted.", "all": ["now is better than never"], "numbers": ["11"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-eric", "q": BOTH + "Quote the Zen line about special cases, and say how many PEP rows list Eric V. Smith as an author.", "all": ["special cases"], "numbers": ["4"], "need": ["research", "data"], "forbid": ["code"]},
    {"id": "p-mix-pablo", "q": BOTH + "Quote the Zen line that says namespaces are a great idea, and say how many PEP rows list Pablo Galindo as an author.", "all": ["namespaces"], "numbers": ["15"], "need": ["research", "data"], "forbid": ["code"]},
]


def workers_in_order(traces: list[dict]) -> list[str]:
    seen: list[str] = []
    for event in traces:
        node = event["node"]
        if event["event"] == "enter" and node in WORKERS and node not in seen:
            seen.append(node)
    return seen


def path_judge(spec: dict, reply: dict) -> tuple[bool, str]:
    traces = reply.get("traces") or []
    routes = reply.get("routes") or []
    found = workers_in_order(traces)
    missing = [agent for agent in spec["need"] if agent not in found]
    extra = [agent for agent in spec["forbid"] if agent in found]
    problems = []
    if missing:
        problems.append("missing worker " + ", ".join(missing))
    if extra:
        problems.append("unexpected worker " + ", ".join(extra))
    order = [(event["node"], event["event"]) for event in traces]
    plan_at = next((index for index, item in enumerate(order) if item == ("plan", "exit")), -1)
    summary_at = next((index for index, item in enumerate(order) if item == ("summary", "enter")), -1)
    if plan_at < 0 or summary_at < 0 or plan_at > summary_at:
        problems.append("plan did not finish before summary")
    for agent in spec["need"]:
        entered = next((index for index, item in enumerate(order) if item == (agent, "enter")), -1)
        if entered < 0 or not (plan_at < entered < summary_at):
            problems.append(f"{agent} was not between the plan and summary")
    if "planner:google" not in routes:
        problems.append("planner did not use Google")
    if "summary:openai" not in routes:
        problems.append("summary did not use OpenAI")
    for agent in spec["need"]:
        expected = "openai" if agent == "code" else "google"
        if f"{agent}:{expected}" not in routes:
            problems.append(f"{agent} did not use {expected}")
    if problems:
        return False, "; ".join(problems)
    return True, "path ok"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    old_questions = {item["q"] for item in SCENARIOS + SCENARIOS_100}
    ids = [item["id"] for item in SCENARIOS_PATH]
    if len(SCENARIOS_PATH) != 100 or len(set(ids)) != 100:
        raise SystemExit(f"expected 100 unique scenarios, found {len(ids)}")
    repeated = [item["id"] for item in SCENARIOS_PATH if item["q"] in old_questions]
    if repeated:
        raise SystemExit(f"questions repeat an earlier set: {repeated}")
    results = []
    if OUT.exists():
        results = json.loads(OUT.read_text(encoding="utf-8")).get("results") or []
    done = {item["id"] for item in results}
    for index, spec in enumerate(SCENARIOS_PATH, start=1):
        if spec["id"] in done:
            continue
        print(f"[{index}/100] {spec['id']}", flush=True)
        reply = _ask(spec["q"])
        if not reply["answer"]:
            reply = _ask(spec["q"])
        answer_ok, answer_reason = judge(spec, reply["answer"])
        route_ok, route_reason = path_judge(spec, reply)
        row = {
            "id": spec["id"],
            "question": spec["q"],
            "need": spec["need"],
            "forbid": spec["forbid"],
            "pass": answer_ok and route_ok,
            "answer_pass": answer_ok,
            "path_pass": route_ok,
            "answer_reason": answer_reason,
            "path_reason": route_reason,
            "workers": workers_in_order(reply.get("traces") or []),
            "routes": reply["routes"],
            "ms": reply["ms"],
            "errors": reply["errors"],
            "answer": reply["answer"],
        }
        results.append(row)
        OUT.write_text(json.dumps({"results": results}, indent=2) + "\n", encoding="utf-8")
        print(
            f"  {'PASS' if row['pass'] else 'FAIL'} answer={answer_reason} path={route_reason} workers={row['workers']}",
            flush=True,
        )
        print("  " + reply["answer"][:220].replace("\n", " "), flush=True)
    both = sum(1 for item in results if item["pass"])
    answers = sum(1 for item in results if item["answer_pass"])
    paths = sum(1 for item in results if item["path_pass"])
    print(f"\n{both}/{len(results)} passed both", flush=True)
    print(f"{answers}/{len(results)} answers right", flush=True)
    print(f"{paths}/{len(results)} paths right", flush=True)
    for item in results:
        if not item["pass"]:
            print(
                f"FAIL {item['id']}: answer={item['answer_reason']} path={item['path_reason']} workers={item['workers']}",
                flush=True,
            )


def _ask(question: str) -> dict:
    try:
        return ask(question)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"answer": "", "routes": [], "traces": [], "errors": [type(exc).__name__], "ms": 0}


if __name__ == "__main__":
    main()
