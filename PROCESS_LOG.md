# Process log

## AI tools used

I built this in Cursor with Grok, working phase by phase from `plan.md`. API keys stayed in a local `.env` file and were never pasted into the chat. The model drafted the graph, the page, the evaluation runner, and these docs. I read the diffs and the saved run files before calling a phase done.

## What worked and where I got stuck

The supervisor graph, the Chroma index, and the two-column page all came together without much trouble. The real obstacles were retrieval and scoring. A rewritten query kept ranking above the PEP 8 imports passage, and that only stopped once chunks from any PEP mentioned in the question were preserved. Next, RAGAS asked Gemini for multiple completions in a single request, which Gemini doesn't support. A second attempt passed `max_tokens` to GPT 6.1 Sol, which also rejected it. Scoring finally worked once the judge stayed on Gemini and each call requested just one completion.

## How I tested beyond "it ran"

Phase scripts check a chunk count, a named PEP hit, a route log, a recovered worker failure, and an SSE stream that emits trace and route before the first token. In the browser I used a starter question, watched tokens arrive while the button was still disabled, opened the `pep-0008/09-imports/0` citation, and checked that a follow-up request included the earlier turn. The twenty-question RAGAS means are in `docs/evaluation.md`.

## What I had to figure out myself

Routing can depend only on how complex the plan is, so the supervisor never sees the question itself. Calls to GPT 6.1 Sol are made through the Responses API. Tavily is reached through a single MCP URL with the key placed in the query string: Research handles the searches, while Summary pulls the content of a URL that Research already returned. `langchain-community` is pinned at 0.4.1 because version 0.4.2 breaks the RAGAS import. Nothing is kept on the server between requests. The browser supplies the history, so refreshing the page starts a fresh conversation.
