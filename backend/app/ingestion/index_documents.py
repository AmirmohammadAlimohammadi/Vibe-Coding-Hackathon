from __future__ import annotations

import argparse
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
from qdrant_client import QdrantClient, models

from app.ingestion.chunker import Chunk, MarkdownChunker
from app.retrieval.sparse import SPARSE_ENCODING_VERSION, payload_search_text, sparse_vector


DEFAULT_COLLECTION = "liara_documentation_hybrid"
DEFAULT_MODEL = "gemini-embedding-2"
DEFAULT_DIMENSIONS = 768
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "keyword"


class RequestRateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        if requests_per_minute < 1:
            raise ValueError("requests_per_minute must be positive")
        self.interval = 60.0 / requests_per_minute
        self.lock = threading.Lock()
        self.next_request_at = 0.0

    def wait(self) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                if now >= self.next_request_at:
                    self.next_request_at = now + self.interval
                    return
                delay = self.next_request_at - now
            time.sleep(min(delay, 1.0))

    def defer(self, delay: float) -> None:
        with self.lock:
            self.next_request_at = max(self.next_request_at, time.monotonic() + delay)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk Liara docs and index them in Qdrant.")
    parser.add_argument("--docs-dir", type=Path, required=True)
    parser.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION))
    parser.add_argument("--model", default=os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL))
    parser.add_argument(
        "--dimensions",
        type=int,
        default=int(os.getenv("EMBEDDING_DIMENSIONS", str(DEFAULT_DIMENSIONS))),
    )
    parser.add_argument("--workers", type=int, default=int(os.getenv("EMBEDDING_WORKERS", "3")))
    parser.add_argument(
        "--requests-per-minute",
        type=int,
        default=int(os.getenv("EMBEDDING_REQUESTS_PER_MINUTE", "120")),
    )
    parser.add_argument("--upsert-batch-size", type=int, default=16)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-embed unchanged points.")
    return parser.parse_args()


def load_environment() -> None:
    candidates = [Path.cwd() / ".env", Path.cwd() / "backend" / ".env"]
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate)


def batched(items: list, size: int) -> Iterable[list]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def parse_retry_delay(value: str | None, fallback: float) -> float:
    if not value:
        return fallback
    try:
        return max(1.0, float(value))
    except ValueError:
        pass
    matches = re.findall(r"([0-9.]+)\s*(ms|s|m)", value.lower())
    if not matches:
        return fallback
    multipliers = {"ms": 0.001, "s": 1.0, "m": 60.0}
    return max(1.0, sum(float(amount) * multipliers[unit] for amount, unit in matches))


def embed_chunk(
    client: OpenAI,
    limiter: RequestRateLimiter,
    chunk: Chunk,
    model: str,
    dimensions: int,
) -> list[float]:
    max_rate_retries = int(os.getenv("AVALAI_MAX_RATE_RETRIES", "20"))
    for attempt in range(max_rate_retries + 1):
        limiter.wait()
        try:
            response = client.embeddings.create(
                model=model,
                input=chunk.embedding_text,
                dimensions=dimensions,
            )
            break
        except RateLimitError as error:
            if attempt == max_rate_retries:
                raise
            headers = error.response.headers
            raw_delay = (
                headers.get("retry-after")
                or headers.get("x-ratelimit-reset-requests")
                or headers.get("x-ratelimit-reset-tokens")
            )
            delay = min(
                65.0,
                parse_retry_delay(raw_delay, min(60.0, 2 ** (attempt + 1))) + 2.0,
            )
            limit = headers.get("x-ratelimit-limit-requests", "unknown")
            remaining = headers.get("x-ratelimit-remaining-requests", "unknown")
            print(
                f"Rate limited; retrying in {delay:.1f}s "
                f"(request limit: {limit}, remaining: {remaining}).",
                flush=True,
            )
            limiter.defer(delay)
    embedding = response.data[0].embedding
    if len(embedding) != dimensions:
        raise ValueError(
            f"Embedding dimension mismatch for {chunk.source_path}: "
            f"expected {dimensions}, received {len(embedding)}"
        )
    return embedding


def ensure_collection(client: QdrantClient, collection: str, dimensions: int) -> None:
    if client.collection_exists(collection):
        info = client.get_collection(collection)
        vectors = info.config.params.vectors
        dense_config = vectors.get(DENSE_VECTOR_NAME) if isinstance(vectors, dict) else None
        actual_size = dense_config.size if dense_config is not None else None
        sparse_vectors = info.config.params.sparse_vectors or {}
        if actual_size != dimensions:
            raise RuntimeError(
                f"Collection {collection!r} does not have a {dimensions}-dimension "
                f"{DENSE_VECTOR_NAME!r} vector. Use the hybrid migration script first."
            )
        if SPARSE_VECTOR_NAME not in sparse_vectors:
            raise RuntimeError(
                f"Collection {collection!r} does not have the "
                f"{SPARSE_VECTOR_NAME!r} sparse vector."
            )
        return

    client.create_collection(
        collection_name=collection,
        vectors_config={
            DENSE_VECTOR_NAME: models.VectorParams(
                size=dimensions,
                distance=models.Distance.COSINE,
            )
        },
        sparse_vectors_config={
            SPARSE_VECTOR_NAME: models.SparseVectorParams(modifier=models.Modifier.IDF)
        },
    )
    for field in ("product_family", "service", "category", "doc_type", "language", "source_path"):
        client.create_payload_index(
            collection_name=collection,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )


def unchanged_point_ids(
    client: QdrantClient,
    collection: str,
    chunks: list[Chunk],
    model: str,
    dimensions: int,
) -> set[str]:
    expected_hashes = {chunk.point_id: chunk.content_hash for chunk in chunks}
    records = client.retrieve(
        collection_name=collection,
        ids=[chunk.point_id for chunk in chunks],
        with_payload=True,
        with_vectors=False,
    )
    unchanged: set[str] = set()
    for record in records:
        payload = record.payload or {}
        point_id = str(record.id)
        if (
            payload.get("content_hash") == expected_hashes.get(point_id)
            and payload.get("embedding_model") == model
            and payload.get("embedding_dimensions") == dimensions
            and payload.get("sparse_encoding_version") == SPARSE_ENCODING_VERSION
        ):
            unchanged.add(point_id)
    return unchanged


def main() -> int:
    load_environment()
    args = parse_args()
    docs_dir = args.docs_dir.resolve()
    if not docs_dir.is_dir():
        raise FileNotFoundError(f"Documentation directory not found: {docs_dir}")

    chunker = MarkdownChunker()
    chunks = chunker.chunk_directory(docs_dir)
    if args.limit is not None:
        chunks = chunks[: args.limit]
    document_count = len({chunk.document_id for chunk in chunks})
    print(f"Prepared {len(chunks)} chunks from {document_count} documents.")
    if chunker.warnings:
        print(f"Parser warnings: {len(chunker.warnings)}")
        for warning in chunker.warnings[:20]:
            print(f"- {warning}")
    if args.dry_run:
        return 0

    api_key = os.getenv("AVALAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("Set AVALAI_API_KEY (or legacy LLM_API_KEY) in backend/.env")

    embedding_client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("AVALAI_BASE_URL", "https://api.avalai.ir/v1"),
        timeout=float(os.getenv("AVALAI_EMBEDDING_TIMEOUT", "60")),
        max_retries=0,
    )
    qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"), timeout=60)
    ensure_collection(qdrant, args.collection, args.dimensions)
    limiter = RequestRateLimiter(args.requests_per_minute)

    indexed_at = datetime.now(UTC).isoformat()
    processed = 0
    embedded = 0
    skipped = 0
    for chunk_batch in batched(chunks, args.upsert_batch_size):
        unchanged = (
            set()
            if args.force
            else unchanged_point_ids(
                qdrant,
                args.collection,
                chunk_batch,
                args.model,
                args.dimensions,
            )
        )
        pending = [chunk for chunk in chunk_batch if chunk.point_id not in unchanged]
        points: list[models.PointStruct] = []
        if pending:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {
                    executor.submit(
                        embed_chunk,
                        embedding_client,
                        limiter,
                        chunk,
                        args.model,
                        args.dimensions,
                    ): chunk
                    for chunk in pending
                }
                for future in as_completed(futures):
                    chunk = futures[future]
                    vector = future.result()
                    payload = chunk.payload()
                    payload["embedding_model"] = args.model
                    payload["embedding_dimensions"] = args.dimensions
                    payload["sparse_encoding_version"] = SPARSE_ENCODING_VERSION
                    payload["indexed_at"] = indexed_at
                    points.append(
                        models.PointStruct(
                            id=chunk.point_id,
                            vector={
                                DENSE_VECTOR_NAME: vector,
                                SPARSE_VECTOR_NAME: sparse_vector(
                                    payload_search_text(payload)
                                ),
                            },
                            payload=payload,
                        )
                    )
            qdrant.upsert(collection_name=args.collection, points=points, wait=True)

        embedded += len(points)
        skipped += len(unchanged)
        processed += len(chunk_batch)
        print(
            f"Processed {processed}/{len(chunks)} chunks "
            f"(embedded {embedded}, unchanged {skipped}).",
            flush=True,
        )

    count = qdrant.count(collection_name=args.collection, exact=True).count
    print(f"Collection {args.collection!r} now contains {count} points.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Ingestion interrupted.", file=sys.stderr)
        raise SystemExit(130)
