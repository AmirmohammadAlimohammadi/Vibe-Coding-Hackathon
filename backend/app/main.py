from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.retrieval.agentic_rag import AgenticRagService, SearchAttempt


logger = logging.getLogger(__name__)

app = FastAPI(
    title="Liara Chatbot Backend",
    description="Backend API for the hosting assistant chatbot.",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"message": "Liara chatbot backend is running."}


class RagQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    max_refinements: int = Field(default=2, ge=0, le=2)


class RagSource(BaseModel):
    citation_number: int
    point_id: str
    score: float
    source_path: str
    source_url: str
    document_title: str
    heading_path: list[str]


class RagQueryResponse(BaseModel):
    answer: str
    model: str
    final_search_query: str
    evidence_sufficient: bool
    attempts: list[SearchAttempt]
    sources: list[RagSource]


@lru_cache(maxsize=1)
def rag_service() -> AgenticRagService:
    return AgenticRagService()


@app.post("/rag/query", response_model=RagQueryResponse, tags=["rag"])
def query_documentation(request: RagQueryRequest) -> RagQueryResponse:
    try:
        service = rag_service()
        state = service.query(request.question, request.max_refinements)
    except Exception as error:
        logger.exception("RAG query failed")
        raise HTTPException(
            status_code=502,
            detail="The documentation retrieval service is temporarily unavailable.",
        ) from error

    sources: list[RagSource] = []
    for citation_number, document in enumerate(state["documents"], start=1):
        sources.append(
            RagSource(
                citation_number=citation_number,
                point_id=document.point_id,
                score=document.score,
                source_path=document.source_path,
                source_url=document.source_url,
                document_title=document.document_title,
                heading_path=document.heading_path,
            )
        )

    return RagQueryResponse(
        answer=state["answer"],
        model=service.model_name,
        final_search_query=state["search_query"],
        evidence_sufficient=state["sufficient"],
        attempts=state["attempts"],
        sources=sources,
    )
