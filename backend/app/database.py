from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql://chatbot:chatbot@localhost:5432/chatbot",
    )
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(
    database_url(),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def initialize_database() -> None:
    from app.chat import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def close_database() -> None:
    engine.dispose()


def get_database_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
