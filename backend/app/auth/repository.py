from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.models import User


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def get_or_create_verified_user(session: Session, email: str) -> User:
    now = datetime.now(UTC)
    statement = (
        insert(User)
        .values(
            email=normalize_email(email),
            email_verified_at=now,
            last_login_at=now,
        )
        .on_conflict_do_update(
            index_elements=[User.email],
            set_={
                "email_verified_at": now,
                "last_login_at": now,
            },
        )
        .returning(User)
    )
    user = session.scalar(statement)
    session.commit()
    if user is None:
        raise RuntimeError("Unable to create or load the verified user")
    return user


def get_user_by_id(session: Session, user_id: uuid.UUID) -> User | None:
    return session.scalar(select(User).where(User.id == user_id))
