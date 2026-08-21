# Chatbot cost optimization

## Optimized request path

1. Enforce atomic per-user and global request, concurrency, and daily token budgets in Redis.
2. Return an exact cached answer when the question has no history or sensitive values.
3. Rewrite only short or reference-dependent follow-ups with `gpt-5-nano`.
4. Return cached retrieval results when available.
5. Run local Qdrant sparse search first for distinctive technical identifiers.
6. Use a cached query embedding or request one only when hybrid search is still necessary.
7. Make one combined decision-and-answer call instead of separate grading and answer calls.
8. Route ordinary questions to `gpt-5-mini` and complex questions to `gpt-5.6-terra`.
9. Allow at most one refinement and otherwise clarify or refuse without guessing.
10. Record actual model token metadata, calls, cache hits, strategy, and latency context.

Compared with the previous path, an uncached simple question drops from one embedding plus
two Terra calls to zero or one embedding plus one Mini call. An exact cached question makes
no provider request. A clear follow-up no longer pays for contextualization; a dependent
follow-up adds one short Nano call.

## Configuration

| Variable | Default | Purpose |
| --- | ---: | --- |
| `RAG_ROUTER_MODEL` | `gpt-5-nano` | Context-dependent query rewriting |
| `RAG_SIMPLE_MODEL` | `gpt-5-mini` | Ordinary decisions and answers |
| `RAG_COMPLEX_MODEL` | `gpt-5.6-terra` | Complex and operational questions |
| `RAG_ROUTER_MAX_OUTPUT_TOKENS` | `120` | Query rewrite output ceiling |
| `RAG_SIMPLE_MAX_OUTPUT_TOKENS` | `700` | Ordinary response ceiling |
| `RAG_COMPLEX_MAX_OUTPUT_TOKENS` | `1000` | Complex response ceiling |
| `RAG_MAX_CONTEXT_CHARS` | `10000` | Maximum retrieved context |
| `CHAT_MEMORY_MESSAGES` | `6` | Recent messages loaded per turn |
| `CHAT_MEMORY_MAX_CHARS` | `6000` | Maximum recent-history characters |
| `RAG_SPARSE_FIRST` | `true` | Permit safe local sparse-only retrieval |
| `RAG_ANSWER_CACHE_TTL_SECONDS` | `21600` | Exact answer cache lifetime |
| `RAG_RETRIEVAL_CACHE_TTL_SECONDS` | `86400` | Retrieval result lifetime |
| `RAG_EMBEDDING_CACHE_TTL_SECONDS` | `2592000` | Query embedding lifetime |
| `RAG_REQUESTS_PER_MINUTE_PER_USER` | `12` | User burst protection |
| `RAG_REQUESTS_PER_DAY_PER_USER` | `200` | User daily request budget |
| `RAG_TOKENS_PER_DAY_PER_USER` | `100000` | User daily provider-token budget |
| `RAG_ESTIMATED_TOKENS_PER_REQUEST` | `7000` | Atomic pre-request token reservation |
| `RAG_REQUESTS_PER_MINUTE_GLOBAL` | `60` | Global burst protection |
| `RAG_REQUESTS_PER_DAY_GLOBAL` | `2000` | Global daily request budget |
| `RAG_TOKENS_PER_DAY_GLOBAL` | `500000` | Global daily provider-token budget |

Set budgets from the account's actual spend limit before production. The defaults are safety
ceilings, not pricing recommendations.

## Cache safety and invalidation

- Answer cache keys include normalized question, expertise, models, prompt version, index
  version, and refinement budget.
- Answers with chat history or likely credentials are never shared through the answer cache.
- Retrieval keys include collection, embedding model, dimensions, strategy, and index version.
- Increase `RAG_PROMPT_VERSION` whenever answer policy changes.
- Increase `RAG_INDEX_VERSION` after re-ingesting or materially changing the source corpus.
- Redis failures are fail-open for cache and budget infrastructure so availability does not
  depend on optimization state; provider and Qdrant errors still return safe API failures.

## Telemetry

Every successful turn logs and returns:

- selected and used models;
- response action and retrieval strategy;
- answer, retrieval, and embedding cache hits;
- whether contextualization ran;
- LLM and embedding call counts;
- input, output, and total provider tokens.

The same data is stored in assistant-message details. Monitor totals by user and day and alert
before the Avalai account balance reaches its operational reserve.

## Quality controls

- Sparse-only retrieval requires both a distinctive technical term and a minimum Qdrant score.
- Generic questions still use hybrid retrieval.
- Six chunks and 10,000 context characters preserve the tested source window.
- The bilingual golden set validates retrieval, clarification, refusal, memory, citations, and
  personalization before changing thresholds or models.
