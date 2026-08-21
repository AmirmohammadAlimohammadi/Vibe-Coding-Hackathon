from __future__ import annotations

import os

from qdrant_client import QdrantClient


def create_qdrant_client(*, timeout: float) -> QdrantClient:
    api_key = os.getenv("QDRANT_API_KEY") or None
    return QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=api_key,
        timeout=timeout,
    )
