from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.chat import repository
from app.chat.models import MessageRole
from app.chat.schemas import (
    ChatCreateRequest,
    ChatDetailResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSummaryResponse,
    ChatTurnResponse,
    ChatUpdateRequest,
)
from app.database import get_database_session
from app.retrieval.api import serialize_rag_result
from app.retrieval.cost_control import (
    RagBudgetExceededError,
    RagRateLimitError,
    get_rag_cost_guard,
)
from app.retrieval.dependencies import get_rag_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ChatSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_chat(
    request: ChatCreateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_database_session),
) -> ChatSummaryResponse:
    chat = repository.create_chat(session, current_user.id, request.title)
    return ChatSummaryResponse.model_validate(chat)


@router.get("", response_model=list[ChatSummaryResponse])
def list_chats(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_database_session),
) -> list[ChatSummaryResponse]:
    return [
        ChatSummaryResponse(
            id=chat.id,
            title=chat.title,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
            message_count=message_count,
        )
        for chat, message_count in repository.list_chats(
            session,
            current_user.id,
            limit=limit,
            offset=offset,
        )
    ]


@router.get("/{chat_id}", response_model=ChatDetailResponse)
def get_chat(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_database_session),
) -> ChatDetailResponse:
    chat = repository.get_chat(session, current_user.id, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return ChatDetailResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        messages=[ChatMessageResponse.model_validate(message) for message in chat.messages],
    )


@router.patch("/{chat_id}", response_model=ChatSummaryResponse)
def rename_chat(
    chat_id: uuid.UUID,
    request: ChatUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_database_session),
) -> ChatSummaryResponse:
    chat = repository.rename_chat(session, current_user.id, chat_id, request.title)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return ChatSummaryResponse.model_validate(chat)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_database_session),
) -> Response:
    if not repository.delete_chat(session, current_user.id, chat_id):
        raise HTTPException(status_code=404, detail="Chat not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{chat_id}/messages", response_model=ChatTurnResponse)
def send_message(
    chat_id: uuid.UUID,
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_database_session),
) -> ChatTurnResponse:
    if not repository.chat_exists(session, current_user.id, chat_id):
        raise HTTPException(status_code=404, detail="Chat not found")

    history = repository.get_chat_memory(
        session,
        current_user.id,
        chat_id,
        limit=int(os.getenv("CHAT_MEMORY_MESSAGES", "6")),
        max_chars=int(os.getenv("CHAT_MEMORY_MAX_CHARS", "6000")),
    )
    guard = get_rag_cost_guard()
    try:
        lease = guard.acquire(str(current_user.id))
    except (RagRateLimitError, RagBudgetExceededError) as error:
        raise HTTPException(
            status_code=429,
            detail=str(error),
            headers={"Retry-After": str(error.retry_after)},
        ) from error

    try:
        user_message = repository.append_message(
            session,
            current_user.id,
            chat_id,
            MessageRole.USER,
            request.question,
        )
    except Exception:
        guard.settle_tokens(lease, 0)
        guard.release(lease)
        raise
    if user_message is None:
        guard.settle_tokens(lease, 0)
        guard.release(lease)
        raise HTTPException(status_code=404, detail="Chat not found")

    used_tokens = 0
    try:
        service = get_rag_service()
        state = service.query(
            request.question,
            request.max_refinements,
            history=history,
            expertise_level=current_user.expertise_level,
        )
        rag = serialize_rag_result(service, state)
        used_tokens = state["usage"]["total_tokens"]
        logger.info(
            "rag_turn user_id=%s chat_id=%s action=%s model=%s strategy=%s "
            "cache_hit=%s contextualized=%s llm_calls=%s embedding_calls=%s "
            "input_tokens=%s output_tokens=%s total_tokens=%s",
            current_user.id,
            chat_id,
            state["action"],
            state["model_name"],
            state["retrieval_strategy"],
            state["response_cache_hit"],
            state["contextualized"],
            state["usage"]["llm_calls"],
            state["usage"]["embedding_calls"],
            state["usage"]["input_tokens"],
            state["usage"]["output_tokens"],
            state["usage"]["total_tokens"],
        )
    except Exception as error:
        logger.exception("Chat RAG query failed for chat %s", chat_id)
        raise HTTPException(
            status_code=502,
            detail="The documentation retrieval service is temporarily unavailable.",
        ) from error
    finally:
        guard.settle_tokens(lease, used_tokens)
        guard.release(lease)

    assistant_message = repository.append_message(
        session,
        current_user.id,
        chat_id,
        MessageRole.ASSISTANT,
        rag.answer,
        details=rag.model_dump(mode="json", exclude={"answer"}),
    )
    if assistant_message is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    return ChatTurnResponse(
        user_message=ChatMessageResponse.model_validate(user_message),
        assistant_message=ChatMessageResponse.model_validate(assistant_message),
        rag=rag,
    )
