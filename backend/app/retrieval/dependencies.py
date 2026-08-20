from functools import lru_cache

from app.retrieval.agentic_rag import AgenticRagService


@lru_cache(maxsize=1)
def get_rag_service() -> AgenticRagService:
    return AgenticRagService()
