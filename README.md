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
