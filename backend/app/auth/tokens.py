from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt


class TokenError(RuntimeError):
    pass


class AccessTokenService:
    def __init__(self) -> None:
        self.secret = os.getenv("AUTH_TOKEN_SECRET", "")
        if len(self.secret) < 32 or self.secret.startswith("replace-"):
            raise RuntimeError("AUTH_TOKEN_SECRET must contain at least 32 characters")
        self.algorithm = "HS256"
        self.issuer = os.getenv("AUTH_TOKEN_ISSUER", "liara-chatbot")
        self.audience = os.getenv("AUTH_TOKEN_AUDIENCE", "liara-chatbot-web")
        self.expires_seconds = int(os.getenv("AUTH_TOKEN_EXPIRES_SECONDS", "604800"))

    def create(self, user_id: uuid.UUID) -> str:
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "sub": str(user_id),
                "type": "access",
                "iat": now,
                "exp": now + timedelta(seconds=self.expires_seconds),
                "iss": self.issuer,
                "aud": self.audience,
            },
            self.secret,
            algorithm=self.algorithm,
        )

    def decode_subject(self, token: str) -> uuid.UUID:
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["sub", "type", "iat", "exp", "iss", "aud"]},
            )
            if payload["type"] != "access":
                raise TokenError("Unexpected token type")
            return uuid.UUID(payload["sub"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
            raise TokenError("Invalid or expired access token") from error


@lru_cache(maxsize=1)
def get_access_token_service() -> AccessTokenService:
    return AccessTokenService()
