from __future__ import annotations

import json
import logging
import os
import uuid
from collections.abc import Iterator
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
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
from app.retrieval.agentic_rag import RagState
from app.retrieval.dependencies import get_rag_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chats", tags=["chats"])


def server_sent_event(event: str, payload: dict[str, object]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"


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
        limit=int(os.getenv("CHAT_MEMORY_MESSAGES", "20")),
        max_chars=int(os.getenv("CHAT_MEMORY_MAX_CHARS", "16000")),
    )
    user_message = repository.append_message(
        session,
        current_user.id,
        chat_id,
        MessageRole.USER,
        request.question,
    )
    if user_message is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    try:
        service = get_rag_service()
        state = service.query(
            request.question,
            request.max_refinements,
            history=history,
            expertise_level=current_user.expertise_level,
        )
        rag = serialize_rag_result(service, state)
    except Exception as error:
        logger.exception("Chat RAG query failed for chat %s", chat_id)
        raise HTTPException(
            status_code=502,
            detail="The documentation retrieval service is temporarily unavailable.",
        ) from error

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


@router.post(
    "/{chat_id}/messages/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Token stream followed by the persisted assistant message.",
        }
    },
)
def stream_message(
    chat_id: uuid.UUID,
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_database_session),
) -> StreamingResponse:
    if not repository.chat_exists(session, current_user.id, chat_id):
        raise HTTPException(status_code=404, detail="Chat not found")

    history = repository.get_chat_memory(
        session,
        current_user.id,
        chat_id,
        limit=int(os.getenv("CHAT_MEMORY_MESSAGES", "20")),
        max_chars=int(os.getenv("CHAT_MEMORY_MAX_CHARS", "16000")),
    )
    user_message = repository.append_message(
        session,
        current_user.id,
        chat_id,
        MessageRole.USER,
        request.question,
    )
    if user_message is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    def event_stream() -> Iterator[str]:
        yield server_sent_event("status", {"status": "retrieving"})
        try:
            service = get_rag_service()
            for event in service.stream_query(
                request.question,
                request.max_refinements,
                history=history,
                expertise_level=current_user.expertise_level,
            ):
                if event["type"] == "token":
                    yield server_sent_event(
                        "token", {"content": str(event["content"])}
                    )
                    continue

                state = cast(RagState, event["state"])
                rag = serialize_rag_result(service, state)
                assistant_message = repository.append_message(
                    session,
                    current_user.id,
                    chat_id,
                    MessageRole.ASSISTANT,
                    rag.answer,
                    details=rag.model_dump(mode="json", exclude={"answer"}),
                )
                if assistant_message is None:
                    raise RuntimeError("Chat was deleted while the response was streaming")
                yield server_sent_event(
                    "done",
                    {
                        "assistant_message": ChatMessageResponse.model_validate(
                            assistant_message
                        ).model_dump(mode="json"),
                        "rag": rag.model_dump(mode="json"),
                    },
                )
        except Exception:
            logger.exception("Streaming chat RAG query failed for chat %s", chat_id)
            yield server_sent_event(
                "error",
                {
                    "detail": (
                        "The documentation retrieval service is temporarily unavailable."
                    )
                },
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
