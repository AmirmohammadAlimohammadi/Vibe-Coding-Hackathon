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
