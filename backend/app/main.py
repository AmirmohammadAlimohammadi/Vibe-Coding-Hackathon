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
    _: User = Depends(get_current_user),
) -> RagQueryResponse:
    try:
        service = get_rag_service()
        state = service.query(request.question, request.max_refinements)
    except Exception as error:
        logger.exception("RAG query failed")
        raise HTTPException(
            status_code=502,
            detail="The documentation retrieval service is temporarily unavailable.",
        ) from error

    return serialize_rag_result(service, state)
