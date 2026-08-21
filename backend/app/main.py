from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

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

static_files_directory = Path(
    os.getenv("STATIC_FILES_DIR", "/app/static")
).resolve()
static_assets_directory = static_files_directory / "assets"
if static_assets_directory.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=static_assets_directory),
        name="frontend-assets",
    )


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False, response_model=None)
async def root() -> Response:
    index_file = static_files_directory / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return JSONResponse({"message": "Liara chatbot backend is running."})


@app.post("/rag/query", response_model=RagQueryResponse, tags=["rag"])
def query_documentation(
    request: RagQueryRequest,
    current_user: User = Depends(get_current_user),
) -> RagQueryResponse:
    try:
        service = get_rag_service()
        state = service.query(
            request.question,
            request.max_refinements,
            expertise_level=current_user.expertise_level,
        )
    except Exception as error:
        logger.exception("RAG query failed")
        raise HTTPException(
            status_code=502,
            detail="The documentation retrieval service is temporarily unavailable.",
        ) from error

    return serialize_rag_result(service, state)
