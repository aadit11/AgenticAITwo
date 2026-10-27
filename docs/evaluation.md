# Evaluation

Ran on 2026-10-24 over the 20 questions in `eval/questions.json`.
The local warm figures are the representative ones for the 20-question set. They come from this local process after the first question.
Cloud Run cold start is a separate measurement, taken on 2026-10-25 from the public service after the revision became ready.

## RAGAS

The judge is `gemini-3.8-flash`. Answer relevance uses `text-embedding-3-small`.
Each score is the mean over all 20 questions, including the two questions the corpus is not supposed to answer.
The World Cup question is outside the corpus. The desk may answer it from a live web search, so that answer can match the web page and still disagree with the corpus reference.

| Metric | Score |
|---|---|
| Faithfulness | 0.9778 |
| Answer relevance | 0.8497 |
| Context precision | 0.7085 |
| Context recall | 0.9 |

## Latency

Retrieval is the Chroma lookup inside Research, including the embedding call. Questions that never called Research count as zero in the all-questions mean.
LLM time is the sum of the provider calls on that question.
Wall clock is the full graph.
Time to first token is measured from the start of the graph until Summary emits the first token.

| Measure | Milliseconds |
|---|---|
| Mean retrieval, all questions | 687.9 |
| Mean retrieval, questions that called Research | 1250.8 |
| Mean LLM calls | 11837.8 |
| Mean wall clock | 13257.4 |
| Warm time to first token, median of questions after the first | 8383.1 |
| First-question time to first token, local process | 18522.9 |
| Cloud Run cold time to first token, first request on the new revision | 26218.6 |
| Cloud Run warm time to first token, next request on the same instance | 6742.2 |

## Cost

Prices per million tokens, checked 24 Oct 2026: GPT 6.1 Sol $2 input and $10 output, standard tier.
Gemini 3.8 Flash $0.75 input and $3.75 output through 2026-12-31. Thinking tokens are counted as output.

| Provider | Input tokens | Output tokens | Estimated USD |
|---|---|---|---|
| Google `gemini-3.8-flash` | 17740 | 5478 | 0.0338 |
| OpenAI `gpt-6.1-sol` | 18567 | 2383 | 0.061 |

Estimated generation cost per question, averaged across the set: $0.004741.

## Provider comparison

The same three grounded prompts were sent once to each model. This is not the full graph. It compares the cheap model and the strong model on identical evidence.

### imports

- `gemini-3.8-flash` in 2333.8 ms, $0.000204: According to PEP 8, imports should usually be on separate lines. For example, importing each module separately is correct, whereas importing multiple modules on the same line (such as "import sys, os") is wrong.
- `gpt-6.1-sol` in 2164.6 ms, $0.000484: PEP 8 says imports should usually be on separate lines, such as `import os` followed by `import sys`, rather than `import sys, os`.

### final-count

- `gemini-3.8-flash` in 2323.1 ms, $8.6e-05: There are 375 PEPs that have the status Final.
- `gpt-6.1-sol` in 1999.8 ms, $0.000212: 375 PEPs have status Final.

### blank-lines

- `gemini-3.8-flash` in 3101.4 ms, $0.001002: PEP 8 states that top-level function and class definitions should be surrounded with two blank lines, while method definitions inside a class are surrounded by a single blank line.
- `gpt-6.1-sol` in 1536.2 ms, $0.00046: PEP 8 says to surround top-level function and class definitions with two blank lines, and method definitions inside a class with a single blank line.

Gemini cost less on all three prompts. Latency was close: Gemini was faster on the imports prompt, and GPT was faster on the count and blank-lines prompts. Both answers stayed inside the passage and stated the same facts. GPT remains the model for summary and code because those steps are marked high complexity.
