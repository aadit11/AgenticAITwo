# Process log

## AI tools used

I built this in Cursor with Grok, working phase by phase from `plan.md`. API keys stayed in a local `.env` file and were never pasted into the chat. The model drafted the graph, the page, the evaluation runner, and these docs. I read the diffs and the saved run files before calling a phase done.

## What worked and where I got stuck

The supervisor graph, the Chroma index, and the two-column page landed in order. Retrieval and scoring were the stalls. A rewritten query outranked the PEP 8 imports passage until chunks from a PEP named in the question were kept. RAGAS then asked Gemini for several completions at once, which that model rejects, and a second attempt sent `max_tokens` to GPT 6.1 Sol, which that model also rejects. Scores landed after the judge stayed on Gemini and each call asked for one completion.

## How I tested beyond "it ran"

Phase scripts check a chunk count, a named PEP hit, a route log, a recovered worker failure, and an SSE stream that emits trace and route before the first token. In the browser I used a starter question, watched tokens arrive while the button was still disabled, opened the `pep-0008/09-imports/0` citation, and checked that a follow-up request included the earlier turn. The twenty-question RAGAS means are in `docs/evaluation.md`.

## What I had to figure out myself

The router may look only at plan complexity, so the supervisor never reads the question. GPT 6.1 Sol calls go through the Responses API. Tavily uses one MCP URL, with the key in the query string: Research searches, and Summary extracts a URL Research already returned. `langchain-community` stays at 0.4.1 because 0.4.2 breaks the RAGAS import. The server stores nothing between requests. The browser sends history, and a refresh starts over.
