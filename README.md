# Vibe-Coding-Hackathon

Backend scaffold for the Liara hosting assistant chatbot.

## Local stack

Start the FastAPI backend and supporting services:

```bash
docker compose up --build
```

Services:

- FastAPI backend: <http://localhost:8000>
- API health check: <http://localhost:8000/health>
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- Qdrant REST API: <http://localhost:6333>
- Swagger UI: <http://localhost:8000/docs>

## Index the documentation

Copy `backend/.env.example` to `backend/.env`, set `AVALAI_API_KEY`, then build chunks, generate Gemini
Embedding 2 vectors, and upsert them into Qdrant:

```bash
docker compose --profile tools run --rm ingest
```

Ingestion is resumable: unchanged chunks already stored in Qdrant are skipped on
subsequent runs, and AvalAI rate-limit reset headers are respected automatically.

Preview chunk counts without calling the embedding API:

```bash
docker compose --profile tools run --rm ingest --dry-run
```

The ingestion collection contains named `dense` vectors for semantic retrieval and
`keyword` sparse vectors for multilingual lexical retrieval. Qdrant combines both result
sets with reciprocal rank fusion (RRF).

Migrate vectors already stored in the original dense-only collection without calling the
embedding API again:

```bash
docker compose --profile tools run --rm migrate-hybrid
```

After migration, resume ingestion to populate the hybrid collection with the remaining
documentation chunks:

```bash
docker compose --profile tools run --rm ingest --workers 3 --requests-per-minute 100
```

Inspect the first ten chunks returned by Qdrant, including their metadata and full content:

```bash
docker compose --profile tools run --rm inspect-chunks
```

Use `--limit` to request a different number of chunks:

```bash
docker compose --profile tools run --rm inspect-chunks --limit 20
```

Run semantic search and print the five most relevant chunks:

```bash
docker compose --profile tools run --rm search-chunks "How do I fix multiple Django settings files?"
```

Optionally verify that an expected document appears in the results:

```bash
docker compose --profile tools run --rm search-chunks "How do I fix multiple Django settings files?" --expect-source paas/django/fix-common-errors/multiple-settings-files.md
```

## Query the agentic RAG API

Open Swagger UI at <http://localhost:8000/docs> and call `POST /rag/query`, or use:

```bash
curl -X POST http://localhost:8000/rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access-token>" \
  -d '{"question":"چطور خطای Multiple Settings Files جنگو را رفع کنم؟","max_refinements":1}'
```

The optimized LangGraph workflow combines grading and answer generation in one call. It
uses `gpt-5-mini` for ordinary questions, reserves `gpt-5.6-terra` for complex requests,
and uses `gpt-5-nano` only when a context-dependent follow-up must be rewritten. One query
refinement is allowed before the assistant asks for missing details.

Redis caches exact history-free answers, retrieval results, and query embeddings. Distinctive
technical queries use local Qdrant sparse search without requesting a paid embedding; other
queries retain hybrid semantic and keyword retrieval. See `backend/COST_OPTIMIZATION.md` for
budgets, cache invalidation, telemetry, and configuration.

## Persistent chats and memory

Chat history is stored in PostgreSQL using two tables:

- `chats`: UUID, title, creation time, and last-update time.
- `chat_messages`: UUID, chat UUID, role, ordered position, content, timestamps, and JSONB
  metadata containing the model, retrieval attempts, evidence status, and sources.

The backend creates the tables during application startup. Create and select a chat through
Swagger, then send all messages for that conversation to its message endpoint:

```text
POST   /chats
GET    /chats
GET    /chats/{chat_id}
PATCH  /chats/{chat_id}
DELETE /chats/{chat_id}
POST   /chats/{chat_id}/messages
```

For each new turn, the backend loads a bounded recent-memory window. Standalone questions
skip query rewriting entirely; only context-dependent follow-ups use the lightweight router.
The default memory window is six messages and 6,000 characters.

## Email OTP authentication

Users authenticate with their email address only. OTP codes are HMAC-protected in Redis,
expire after five minutes, are single-use, and are limited by email address and client IP.
Configure the `AUTH_*`, `OTP_*`, and `SMTP_*` values from `backend/.env.example` before
using the authentication endpoints:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Run the command twice and use separate values for `AUTH_TOKEN_SECRET` and
`OTP_HASH_SECRET`.

```text
POST /auth/email/request
POST /auth/email/verify
GET  /auth/me
```

The verification endpoint creates the user automatically on their first successful code
verification and returns a bearer access token. Use that token in the `Authorization`
header as `Bearer <token>`. Chat and stateless RAG endpoints require authentication, and
all chat queries are scoped to the authenticated user so returning users see their own
history only.

For local testing without an SMTP provider, explicitly set `EMAIL_DELIVERY_MODE=console`.
This logs OTP codes and must not be enabled in production.

## Frontend

The React frontend is built as a static Vite application and served by Nginx. Nginx proxies
`/api/*` requests to the FastAPI backend, so authentication and chat requests use the same
origin without browser CORS configuration.

```bash
docker compose up --build
```

Open `http://localhost:3000`, enter an email address, verify the emailed OTP, and start a
conversation. The access token is restored from browser storage, previous chats are loaded
for the authenticated user, and new questions are sent to the persistent chat RAG endpoint.
