from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.database import close_database, initialize_database
from app.retrieval.api import RagQueryRequest, RagQueryResponse, serialize_rag_result
from app.retrieval.cost_control import (
    RagBudgetExceededError,
    RagRateLimitError,
    get_rag_cost_guard,
)
from app.retrieval.dependencies import get_rag_service


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield
    close_database()


app = FastAPI(
    title="Liara Chatbot Backend",
    description="Backend API for the hosting assistant chatbot.",
    version="0.1.0",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)
app.include_router(auth_router)
app.include_router(chat_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"message": "Liara chatbot backend is running."}


@app.post("/rag/query", response_model=RagQueryResponse, tags=["rag"])
def query_documentation(
    request: RagQueryRequest,
    current_user: User = Depends(get_current_user),
) -> RagQueryResponse:
    guard = get_rag_cost_guard()
    used_tokens = 0
    try:
        lease = guard.acquire(str(current_user.id))
    except (RagRateLimitError, RagBudgetExceededError) as error:
        raise HTTPException(
            status_code=429,
            detail=str(error),
            headers={"Retry-After": str(error.retry_after)},
        ) from error
    try:
        service = get_rag_service()
        state = service.query(
            request.question,
            request.max_refinements,
            expertise_level=current_user.expertise_level,
        )
        used_tokens = state["usage"]["total_tokens"]
        logger.info(
            "rag_query user_id=%s action=%s model=%s strategy=%s cache_hit=%s "
            "llm_calls=%s embedding_calls=%s total_tokens=%s",
            current_user.id,
            state["action"],
            state["model_name"],
            state["retrieval_strategy"],
            state["response_cache_hit"],
            state["usage"]["llm_calls"],
            state["usage"]["embedding_calls"],
            state["usage"]["total_tokens"],
        )
    except Exception as error:
        logger.exception("RAG query failed")
        raise HTTPException(
            status_code=502,
            detail="The documentation retrieval service is temporarily unavailable.",
        ) from error
    finally:
        guard.settle_tokens(lease, used_tokens)
        guard.release(lease)

    return serialize_rag_result(service, state)
