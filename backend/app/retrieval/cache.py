from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import unicodedata
from typing import Any

from redis import Redis
from redis.exceptions import RedisError


logger = logging.getLogger(__name__)


def normalize_cache_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"\s+", " ", normalized).strip()


def cache_digest(*parts: object) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RedisCache:
    def __init__(self) -> None:
        self.enabled = os.getenv("RAG_CACHE_ENABLED", "true").lower() == "true"
        self.prefix = os.getenv("RAG_CACHE_PREFIX", "rag")
        self.redis = Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

    def key(self, namespace: str, *parts: object) -> str:
        return f"{self.prefix}:{namespace}:{cache_digest(*parts)}"

    def get_bytes(self, key: str) -> bytes | None:
        if not self.enabled:
            return None
        try:
            value = self.redis.get(key)
            return bytes(value) if value is not None else None
        except RedisError:
            logger.warning("Redis cache read failed", exc_info=True)
            return None

    def set_bytes(self, key: str, value: bytes, ttl_seconds: int) -> None:
        if not self.enabled or ttl_seconds <= 0:
            return
        try:
            self.redis.set(key, value, ex=ttl_seconds)
        except RedisError:
            logger.warning("Redis cache write failed", exc_info=True)

    def get_json(self, key: str) -> Any | None:
        value = self.get_bytes(key)
        if value is None:
            return None
        try:
            return json.loads(value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("Ignoring invalid cached JSON for %s", key)
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self.set_bytes(key, payload, ttl_seconds)
