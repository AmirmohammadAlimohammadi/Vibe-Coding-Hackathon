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
  -d '{"question":"چطور خطای Multiple Settings Files جنگو را رفع کنم؟","max_refinements":2}'
```

The LangGraph workflow runs hybrid retrieval, grades whether the evidence is sufficient,
and can refine and retry the search query up to two times before `gpt-5.6-terra` generates
a grounded answer with sources.

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
POST   /chats/{chat_id}/messages/stream
```

The streaming endpoint uses authenticated Server-Sent Events. It emits `status`, `token`,
`done`, and `error` events; the frontend appends every `token` event immediately and
replaces the temporary message with the persisted assistant message after `done`.

For each new turn, the backend loads recent messages from the selected chat, rewrites
context-dependent follow-up questions into standalone retrieval queries, and gives the
conversation history to the grading and answer-generation steps. The memory window is
bounded by `CHAT_MEMORY_MESSAGES` and `CHAT_MEMORY_MAX_CHARS`.

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

## Deploy to Liara

Liara does not run this repository's Docker Compose stack directly. The production root
`Dockerfile` packages React and FastAPI into one GitHub-deployable application, while Liara
managed PostgreSQL and Redis and a separate disk-backed Qdrant application provide storage.

Follow the complete migration and deployment checklist in `deploy/liara/README.md`.
