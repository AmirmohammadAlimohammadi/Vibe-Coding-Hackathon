from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.chat.models import Chat, ChatMessage, MessageRole


def create_chat(session: Session, user_id: uuid.UUID, title: str | None = None) -> Chat:
    chat = Chat(
        user_id=user_id,
        title=(title or "New chat").strip() or "New chat",
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return chat


def list_chats(
    session: Session,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> list[tuple[Chat, int]]:
    message_count = (
        select(func.count(ChatMessage.id))
        .where(ChatMessage.chat_id == Chat.id)
        .correlate(Chat)
        .scalar_subquery()
    )
    statement = (
        select(Chat, message_count.label("message_count"))
        .where(Chat.user_id == user_id)
        .order_by(Chat.updated_at.desc(), Chat.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.execute(statement).all())


def get_chat(session: Session, user_id: uuid.UUID, chat_id: uuid.UUID) -> Chat | None:
    statement = (
        select(Chat)
        .where(Chat.id == chat_id, Chat.user_id == user_id)
        .options(selectinload(Chat.messages))
    )
    return session.scalar(statement)


def chat_exists(session: Session, user_id: uuid.UUID, chat_id: uuid.UUID) -> bool:
    return (
        session.scalar(
            select(Chat.id).where(Chat.id == chat_id, Chat.user_id == user_id)
        )
        is not None
    )


def rename_chat(
    session: Session,
    user_id: uuid.UUID,
    chat_id: uuid.UUID,
    title: str,
) -> Chat | None:
    chat = session.scalar(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
    )
    if chat is None:
        return None
    chat.title = title.strip()
    chat.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(chat)
    return chat


def delete_chat(session: Session, user_id: uuid.UUID, chat_id: uuid.UUID) -> bool:
    chat = session.scalar(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
    )
    if chat is None:
        return False
    session.delete(chat)
    session.commit()
    return True


def append_message(
    session: Session,
    user_id: uuid.UUID,
    chat_id: uuid.UUID,
    role: MessageRole,
    content: str,
    details: dict | None = None,
) -> ChatMessage | None:
    chat = session.scalar(
        select(Chat)
        .where(Chat.id == chat_id, Chat.user_id == user_id)
        .with_for_update()
    )
    if chat is None:
        return None

    last_position = session.scalar(
        select(func.max(ChatMessage.position)).where(ChatMessage.chat_id == chat_id)
    )
    message = ChatMessage(
        chat_id=chat_id,
        role=role,
        content=content,
        position=(last_position or 0) + 1,
        details=details or {},
    )
    if role == MessageRole.USER and chat.title == "New chat":
        chat.title = content.strip().replace("\n", " ")[:80]
    chat.updated_at = datetime.now(UTC)
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def get_chat_memory(
    session: Session,
    user_id: uuid.UUID,
    chat_id: uuid.UUID,
    *,
    limit: int,
    max_chars: int,
) -> list[dict[str, Any]]:
    statement = (
        select(ChatMessage)
        .join(Chat, Chat.id == ChatMessage.chat_id)
        .where(ChatMessage.chat_id == chat_id, Chat.user_id == user_id)
        .order_by(ChatMessage.position.desc())
        .limit(limit)
    )
    messages = list(reversed(session.scalars(statement).all()))
    memory: list[dict[str, Any]] = []
    used_chars = 0
    for message in reversed(messages):
        if memory and used_chars + len(message.content) > max_chars:
            break
        memory_message = {"role": message.role.value, "content": message.content}
        if message.role == MessageRole.ASSISTANT:
            attempts = message.details.get("attempts", [])
            last_action = attempts[-1].get("action") if attempts else None
            memory_message["clarification"] = message.details.get(
                "clarification",
                bool(
                    not message.details.get("evidence_sufficient", True)
                    and last_action not in {None, "refuse"}
                ),
            )
        memory.append(memory_message)
        used_chars += len(message.content)
    return list(reversed(memory))
