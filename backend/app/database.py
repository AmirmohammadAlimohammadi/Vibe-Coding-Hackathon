from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
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
    from app.auth import models as auth_models  # noqa: F401
    from app.chat import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_existing_chats_to_user_ownership()


def _migrate_existing_chats_to_user_ownership() -> None:
    inspector = inspect(engine)
    if "chats" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("chats")}
    with engine.begin() as connection:
        if "user_id" not in columns:
            connection.execute(text("ALTER TABLE chats ADD COLUMN user_id UUID"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_chats_user_id ON chats (user_id)")
        )
        connection.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_chats_user_id_users'
                    ) THEN
                        ALTER TABLE chats
                        ADD CONSTRAINT fk_chats_user_id_users
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
                    END IF;
                END $$;
                """
            )
        )


def close_database() -> None:
    engine.dispose()


def get_database_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
