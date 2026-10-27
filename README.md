# Multi-agent PEP briefing desk

A supervisor LangGraph answers questions about the Python 3.15 docs, the PEP corpus, a PEP table, and a small source bundle. Research, Data, and Code do the specialist work. Summary writes the final answer. The page streams tokens, a live trace, the provider route, and citation chips.

The field that chooses the next agent is `next_node`. See `docs/architecture.md`.

## Local setup

Python 3.13. From the repo root:

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

macOS or Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with your own keys. Do not commit `.env`.

Ingest is a one-time local step. It is not part of server startup. The download and the embedding call need a network connection, and `build_index.py` spends the OpenAI embedding key.

```bash
python -m ingest.download_corpus
python -m ingest.build_index
python -m ingest.build_sqlite
```

`build_index.py --dry-run` chunks without calling the embedding API. `build_index.py --smoke` queries the index that is already on disk. The checked-in snapshot is 2026-10-24: 1,161 documents and 41,929 chunks in `./chroma_index`, plus `data/peps.sqlite`. Those generated files are gitignored. A deploy image has to contain them. See `docs/architecture.md` for the corpus, chunk size, overlap, and `k`.

## Environment variables

Copy `.env.example`. Generation providers are pinned to two companies.

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | GPT 6.1 Sol and `text-embedding-3-small` |
| `OPENAI_MODEL` | `gpt-6.1-sol`. Capability route: synthesis, summary, and code. Responses API. Do not use Ultrafast. |
| `GOOGLE_API_KEY` | Gemini |
| `GEMINI_MODEL` | `gemini-3.8-flash`. Cost route: planning, query rewrite, and short lookups. |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small`. Embeddings only. Not a second generation provider. |
| `TAVILY_API_KEY` | Query parameter on the shared Tavily Remote MCP URL. Never a request body. |
| `CHROMA_PERSIST_DIR` | Default `./chroma_index` |
| `SQLITE_PATH` | Default `./data/peps.sqlite` |
| `CODE_BUNDLE_DIR` | Default `./code_bundle` |
| `GCP_PROJECT_ID` | Cloud Run project |
| `GCP_REGION` | `us-west1` |
| `CLOUD_RUN_SERVICE` | `multi-agent-rag` |

## Run locally

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. `GET /health` returns `ok`, `chroma_count`, and `providers_configured`. It does not return key values. The server stores no conversation. The page sends `history` with each question, and a refresh starts over.

## Deploy to Cloud Run

Use a fresh project id. These commands enable the APIs, build from the repo `Dockerfile`, and set runtime env vars. Do not bake keys into the image. Replace the three key placeholders. Leave the model ids as written.

```bash
gcloud config set project PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

gcloud run deploy multi-agent-rag \
  --source . \
  --region us-west1 \
  --timeout 300 \
  --memory 2Gi \
  --cpu 1 \
  --concurrency 10 \
  --min-instances 0 \
  --max-instances 3 \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=YOUR_OPENAI_KEY,OPENAI_MODEL=gpt-6.1-sol,GOOGLE_API_KEY=YOUR_GOOGLE_KEY,GEMINI_MODEL=gemini-3.8-flash,OPENAI_EMBEDDING_MODEL=text-embedding-3-small,TAVILY_API_KEY=YOUR_TAVILY_KEY,CHROMA_PERSIST_DIR=./chroma_index,SQLITE_PATH=./data/peps.sqlite,CODE_BUNDLE_DIR=./code_bundle
```

Cloud Run sets `PORT`. The container listens on `0.0.0.0` and that port. After the URL prints, open it in a browser and check `/health`.

The deployed service is https://multi-agent-rag-749179608015.us-west1.run.app. On 2026-10-25 its first request streamed. Cold time to first token was 26218.6 ms, and the next request on the same instance was 6742.2 ms. `/health` reported 41,929 chunks.

## Cost notes

Prices checked 24 Oct 2026.

| Provider | Price | How this app uses it |
|---|---|---|
| OpenAI `gpt-6.1-sol` | $2 / million input tokens, $10 / million output tokens, standard tier | High-complexity summary and code. Not Ultrafast. |
| Google `gemini-3.8-flash` | $0.75 / million input tokens, $3.75 / million output tokens through 2026-12-31 | Low-complexity planning, rewrite, and lookup. Thinking tokens count as output. |
| OpenAI `text-embedding-3-small` | Embedding price, separate from the generation totals below | Ingest and retrieval. Not included in the per-question generation estimate. |
| Tavily | 1 credit for a basic search. 1 credit per 5 successful basic extracts. Free plan is 1,000 credits/month. Pay-as-you-go is $0.008 per credit. | Research and Summary both call basic `tavily_search` with different queries. Summary also calls basic `tavily_extract` on one URL Research already returned. Source: [Tavily credits](https://docs.tavily.com/documentation/api-credits). |

On the 20-question local run, generation cost averaged $0.004741 per question. The split, the RAGAS scores, and the Cloud Run cold and warm times are in `docs/evaluation.md`.
