from __future__ import annotations

from pydantic import BaseModel, Field

from app.retrieval.agentic_rag import AgenticRagService, RagState, SearchAttempt


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


def serialize_rag_result(
    service: AgenticRagService,
    state: RagState,
) -> RagQueryResponse:
    sources = [
        RagSource(
            citation_number=citation_number,
            point_id=document.point_id,
            score=document.score,
            source_path=document.source_path,
            source_url=document.source_url,
            document_title=document.document_title,
            heading_path=document.heading_path,
        )
        for citation_number, document in enumerate(state["documents"], start=1)
    ]
    return RagQueryResponse(
        answer=state["answer"],
        model=service.model_name,
        final_search_query=state["search_query"],
        evidence_sufficient=state["sufficient"],
        attempts=state["attempts"],
        sources=sources,
    )
