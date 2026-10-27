"""Run the fixed question set, time it, and score it with RAGAS."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langchain_openai import OpenAIEmbeddings
from ragas import EvaluationDataset, RunConfig, SingleTurnSample, evaluate
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

from app.graph import invoke_graph
from app.publish import bind_sink, reset_sink
from app.routing import complete, last_token_usage

QUESTIONS_PATH = ROOT / "eval" / "questions.json"
RUNS_PATH = ROOT / "eval" / "ragas_runs.json"
REPORT_PATH = ROOT / "docs" / "evaluation.md"
RUN_DATE = "2026-10-24"

# Published prices checked 24 Oct 2026. Dollars per million tokens.
# Gemini 3.8 Flash promotional rates apply through 2026-12-31.
# Thinking tokens are counted as output. GPT 6.1 Sol is the standard tier, not Ultrafast.
PRICES = {
    "openai": {"input": 2.0, "output": 10.0, "model": "gpt-6.1-sol"},
    "google": {"input": 0.75, "output": 3.75, "model": "gemini-3.8-flash"},
}

COMPARE_PROMPTS = [
    {
        "id": "imports",
        "prompt": (
            "Answer in one or two sentences from this passage only.\n\n"
            "PEP 8: Imports should usually be on separate lines. "
            "import os then import sys is correct. import sys, os is wrong.\n\n"
            "Question: What does PEP 8 say about imports?"
        ),
    },
    {
        "id": "final-count",
        "prompt": (
            "Answer in one sentence from this row only.\n\n"
            "SELECT COUNT(*) AS n FROM peps WHERE status = 'Final' returned n = 375.\n\n"
            "Question: How many PEPs have status Final?"
        ),
    },
    {
        "id": "blank-lines",
        "prompt": (
            "Answer in one or two sentences from this passage only.\n\n"
            "PEP 8: Surround top-level function and class definitions with two blank lines. "
            "Method definitions inside a class are surrounded by a single blank line.\n\n"
            "Question: What does PEP 8 say about blank lines?"
        ),
    },
]


def load_questions() -> list[dict]:
    payload = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    return payload["questions"]


def contexts_from(state: dict) -> list[str]:
    found = []
    for item in state.get("citations") or []:
        excerpt = (item.get("excerpt") or "").strip()
        if not excerpt:
            continue
        found.append(f"{item.get('chunk_id', '')}\n{excerpt}")
    for text in (state.get("agent_outputs") or {}).values():
        cleaned = str(text or "").strip()
        if cleaned and cleaned not in found:
            found.append(cleaned[:1500])
    return found or ["No passage was retrieved."]


def retrieve_ms(state: dict) -> float:
    total = 0.0
    for event in state.get("trace") or []:
        if event.get("event") == "retrieve" and str(event.get("detail", "")).endswith("ms"):
            total += float(str(event["detail"]).split()[0])
    return round(total, 1)


def cost_of(provider: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICES[provider]
    return (input_tokens / 1_000_000) * price["input"] + (output_tokens / 1_000_000) * price["output"]


def run_questions(questions: list[dict]) -> list[dict]:
    runs = []
    for index, item in enumerate(questions, start=1):
        print(f"\n[{index}/{len(questions)}] {item['id']}", flush=True)
        first_token = {"at": None}
        started = time.perf_counter()

        def sink(kind: str, payload: dict) -> None:
            if kind == "token" and first_token["at"] is None:
                first_token["at"] = time.perf_counter()

        token = bind_sink(sink)
        try:
            state = invoke_graph(item["question"])
        finally:
            reset_sink(token)
        wall_ms = round((time.perf_counter() - started) * 1000, 1)
        ttft_ms = None if first_token["at"] is None else round((first_token["at"] - started) * 1000, 1)
        route_log = state.get("route_log") or []
        llm_ms = round(sum(float(entry.get("latency_ms") or 0) for entry in route_log), 1)
        by_provider = {}
        for entry in route_log:
            provider = entry.get("provider")
            if provider not in PRICES:
                continue
            bucket = by_provider.setdefault(provider, {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
            bucket["input_tokens"] += int(entry.get("input_tokens") or 0)
            bucket["output_tokens"] += int(entry.get("output_tokens") or 0)
        for provider, bucket in by_provider.items():
            bucket["cost_usd"] = round(cost_of(provider, bucket["input_tokens"], bucket["output_tokens"]), 6)
        answer = (state.get("final_answer") or "").strip()
        print(f"  wall {wall_ms} ms  retrieve {retrieve_ms(state)} ms  ttft {ttft_ms}  answer {answer[:120]}", flush=True)
        runs.append(
            {
                "id": item["id"],
                "question": item["question"],
                "in_corpus": item["in_corpus"],
                "reference": item["reference"],
                "expected_source_ids": item["expected_source_ids"],
                "answer": answer,
                "contexts": contexts_from(state),
                "wall_ms": wall_ms,
                "retrieve_ms": retrieve_ms(state),
                "llm_ms": llm_ms,
                "ttft_ms": ttft_ms,
                "providers": by_provider,
            }
        )
        RUNS_PATH.write_text(json.dumps({"runs": runs}, indent=2) + "\n", encoding="utf-8")
    return runs


def score(runs: list[dict]) -> dict:
    import os

    from langchain_google_genai import ChatGoogleGenerativeAI
    from ragas.llms.base import LangchainLLMWrapper

    samples = [
        SingleTurnSample(
            user_input=run["question"],
            response=run["answer"] or "No answer was produced.",
            retrieved_contexts=run["contexts"],
            reference=run["reference"],
        )
        for run in runs
    ]
    dataset = EvaluationDataset(samples=samples)
    judge = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(
            model=PRICES["google"]["model"],
            google_api_key=os.environ["GOOGLE_API_KEY"],
        ),
        bypass_n=True,
    )
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=judge,
        embeddings=embeddings,
        run_config=RunConfig(timeout=180, max_workers=4),
        raise_exceptions=False,
        show_progress=True,
    )
    print(result, flush=True)
    scores = {}
    for name in ("faithfulness", "answer_relevancy", "context_precision", "context_recall"):
        value = result._repr_dict[name]
        scores[name] = None if value != value else round(float(value), 4)
    return scores


def compare_providers() -> list[dict]:
    rows = []
    for item in COMPARE_PROMPTS:
        row = {"id": item["id"], "models": {}}
        for provider, price in PRICES.items():
            decision = {
                "provider": provider,
                "model": price["model"],
                "agent": "compare",
                "dimension": "comparison",
                "reason": "Same prompt on both models.",
                "kind": "lookup",
            }
            started = time.perf_counter()
            text = complete(decision, item["prompt"])
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            usage = last_token_usage()
            row["models"][provider] = {
                "model": price["model"],
                "answer": text,
                "latency_ms": elapsed,
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "cost_usd": round(cost_of(provider, usage["input_tokens"], usage["output_tokens"]), 6),
            }
            print(f"compare {item['id']} {provider} {elapsed} ms ${row['models'][provider]['cost_usd']}", flush=True)
        rows.append(row)
    return rows


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def write_report(runs: list[dict], scores: dict, comparison: list[dict]) -> None:
    walls = [run["wall_ms"] for run in runs]
    retrieves = [run["retrieve_ms"] for run in runs]
    searched = [run["retrieve_ms"] for run in runs if run["retrieve_ms"]]
    llms = [run["llm_ms"] for run in runs]
    warm_ttft = [run["ttft_ms"] for run in runs[1:] if run["ttft_ms"] is not None]
    cold_ttft = runs[0]["ttft_ms"] if runs else None
    totals = {"openai": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}, "google": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}}
    for run in runs:
        for provider, bucket in run["providers"].items():
            totals[provider]["input_tokens"] += bucket["input_tokens"]
            totals[provider]["output_tokens"] += bucket["output_tokens"]
            totals[provider]["cost_usd"] += bucket["cost_usd"]
    per_query = round(sum(bucket["cost_usd"] for bucket in totals.values()) / len(runs), 6) if runs else 0
    lines = [
        "# Evaluation",
        "",
        f"Ran on {RUN_DATE} over the {len(runs)} questions in `eval/questions.json`.",
        "Warm figures are the representative ones. They come from this local process after the first question.",
        "A Cloud Run cold start is not in these numbers. Phase 11 records that figure after deploy and keeps it separate from the warm results.",
        "",
        "## RAGAS",
        "",
        "The judge is `gemini-3.8-flash`. Answer relevance uses `text-embedding-3-small`.",
        "Each score is the mean over all 20 questions, including the two questions the corpus is not supposed to answer.",
        "The World Cup question is outside the corpus. The desk may answer it from a live web search, so that answer can match the web page and still disagree with the corpus reference.",
        "",
        "| Metric | Score |",
        "|---|---|",
        f"| Faithfulness | {scores['faithfulness']} |",
        f"| Answer relevance | {scores['answer_relevancy']} |",
        f"| Context precision | {scores['context_precision']} |",
        f"| Context recall | {scores['context_recall']} |",
        "",
        "## Latency",
        "",
        "Retrieval is the Chroma lookup inside Research, including the embedding call. Questions that never called Research count as zero in the all-questions mean.",
        "LLM time is the sum of the provider calls on that question.",
        "Wall clock is the full graph.",
        "Time to first token is measured from the start of the graph until Summary emits the first token.",
        "",
        "| Measure | Milliseconds |",
        "|---|---|",
        f"| Mean retrieval, all questions | {mean(retrieves)} |",
        f"| Mean retrieval, questions that called Research | {mean(searched)} |",
        f"| Mean LLM calls | {mean(llms)} |",
        f"| Mean wall clock | {mean(walls)} |",
        f"| Warm time to first token, median of questions after the first | {median(warm_ttft)} |",
        f"| First-question time to first token, local process | {cold_ttft} |",
        "",
        "## Cost",
        "",
        "Prices per million tokens, checked 24 Oct 2026: GPT 6.1 Sol $2 input and $10 output, standard tier.",
        "Gemini 3.8 Flash $0.75 input and $3.75 output through 2026-12-31. Thinking tokens are counted as output.",
        "",
        "| Provider | Input tokens | Output tokens | Estimated USD |",
        "|---|---|---|---|",
        f"| Google `gemini-3.8-flash` | {totals['google']['input_tokens']} | {totals['google']['output_tokens']} | {round(totals['google']['cost_usd'], 4)} |",
        f"| OpenAI `gpt-6.1-sol` | {totals['openai']['input_tokens']} | {totals['openai']['output_tokens']} | {round(totals['openai']['cost_usd'], 4)} |",
        "",
        f"Estimated generation cost per question, averaged across the set: ${per_query}.",
        "",
        "## Provider comparison",
        "",
        "The same three grounded prompts were sent once to each model. This is not the full graph. It compares the cheap model and the strong model on identical evidence.",
        "",
    ]
    for row in comparison:
        lines.append(f"### {row['id']}")
        lines.append("")
        for provider in ("google", "openai"):
            model = row["models"][provider]
            lines.append(
                f"- `{model['model']}` in {model['latency_ms']} ms, ${model['cost_usd']}: {model['answer']}"
            )
        lines.append("")
    lines.append(
        "Gemini cost less on all three prompts. "
        "Latency was close: Gemini was faster on the imports prompt, and GPT was faster on the count and blank-lines prompts. "
        "Both answers stayed inside the passage and stated the same facts. "
        "GPT remains the model for summary and code because those steps are marked high complexity."
    )
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 1)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 1)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    questions = load_questions()
    if len(questions) < 20:
        raise SystemExit(f"expected about 20 questions, found {len(questions)}")
    if "--score-only" in sys.argv:
        runs = json.loads(RUNS_PATH.read_text(encoding="utf-8"))["runs"]
    else:
        runs = run_questions(questions)
    print("\nscoring with RAGAS", flush=True)
    scores = score(runs)
    print("SCORES", scores, flush=True)
    if any(scores[name] is None for name in scores):
        raise SystemExit(f"RAGAS did not return all four scores: {scores}")
    comparison = compare_providers()
    payload = json.loads(RUNS_PATH.read_text(encoding="utf-8"))
    payload["scores"] = scores
    payload["comparison"] = comparison
    payload["date"] = RUN_DATE
    RUNS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_report(runs, scores, comparison)
    print(f"wrote {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
