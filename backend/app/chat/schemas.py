from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.chat.models import MessageRole
from app.retrieval.api import RagQueryResponse


class ChatCreateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)


class ChatUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ChatSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chat_id: uuid.UUID
    role: MessageRole
    content: str
    position: int
    details: dict[str, Any]
    created_at: datetime


class ChatDetailResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponse]


class ChatMessageRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    max_refinements: int = Field(default=2, ge=0, le=2)


class ChatTurnResponse(BaseModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    rag: RagQueryResponse
