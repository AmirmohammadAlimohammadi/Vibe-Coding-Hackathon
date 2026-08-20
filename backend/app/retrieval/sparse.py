from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter

from qdrant_client import models


TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
SPARSE_ENCODING_VERSION = "hashed-unicode-v1"


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return (
        normalized.replace("ي", "ی")
        .replace("ك", "ک")
        .replace("ۀ", "ه")
        .replace("ة", "ه")
        .replace("\u200c", " ")
        .replace("\u200f", " ")
    )


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(normalize_text(text))


def token_index(token: str) -> int:
    digest = hashlib.blake2s(token.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, byteorder="little", signed=False)


def sparse_vector(text: str, *, is_query: bool = False) -> models.SparseVector:
    counts = Counter(tokenize(text))
    weighted: dict[int, float] = {}
    for token, count in counts.items():
        index = token_index(token)
        value = 1.0 if is_query else 1.0 + math.log(count)
        weighted[index] = weighted.get(index, 0.0) + value

    indices = sorted(weighted)
    return models.SparseVector(
        indices=indices,
        values=[weighted[index] for index in indices],
    )


def payload_search_text(payload: dict) -> str:
    heading_path = payload.get("heading_path") or []
    return "\n".join(
        part
        for part in (
            str(payload.get("document_title") or ""),
            " > ".join(str(item) for item in heading_path),
            str(payload.get("content") or ""),
        )
        if part
    )
