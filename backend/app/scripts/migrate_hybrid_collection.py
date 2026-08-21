from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import models

from app.ingestion.index_documents import (
    DEFAULT_COLLECTION,
    DEFAULT_DIMENSIONS,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    ensure_collection,
)
from app.qdrant import create_qdrant_client
from app.retrieval.sparse import SPARSE_ENCODING_VERSION, payload_search_text, sparse_vector


def load_environment() -> None:
    candidates = [Path.cwd() / ".env", Path.cwd() / "backend" / ".env"]
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy dense points into a dense+sparse Qdrant collection."
    )
    parser.add_argument("--source", default="liara_documentation")
    parser.add_argument(
        "--target",
        default=os.getenv("QDRANT_HYBRID_COLLECTION", DEFAULT_COLLECTION),
    )
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--dimensions",
        type=int,
        default=int(os.getenv("EMBEDDING_DIMENSIONS", str(DEFAULT_DIMENSIONS))),
    )
    return parser.parse_args()


def dense_vector(record: models.Record) -> list[float]:
    vector = record.vector
    if isinstance(vector, list):
        return vector
    if isinstance(vector, dict):
        named = vector.get(DENSE_VECTOR_NAME) or vector.get("")
        if isinstance(named, list):
            return named
    raise RuntimeError(f"Point {record.id} does not contain a dense vector")


def main() -> int:
    load_environment()
    args = parse_args()
    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")
    if args.source == args.target:
        raise ValueError("Source and target collection names must be different")

    client = create_qdrant_client(timeout=60)
    if not client.collection_exists(args.source):
        raise RuntimeError(f"Source collection {args.source!r} does not exist")
    ensure_collection(client, args.target, args.dimensions)

    offset = None
    migrated = 0
    while True:
        records, offset = client.scroll(
            collection_name=args.source,
            limit=args.batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        if not records:
            break

        points: list[models.PointStruct] = []
        for record in records:
            payload = dict(record.payload or {})
            payload["sparse_encoding_version"] = SPARSE_ENCODING_VERSION
            points.append(
                models.PointStruct(
                    id=record.id,
                    vector={
                        DENSE_VECTOR_NAME: dense_vector(record),
                        SPARSE_VECTOR_NAME: sparse_vector(payload_search_text(payload)),
                    },
                    payload=payload,
                )
            )
        client.upsert(
            collection_name=args.target,
            points=points,
            wait=True,
        )
        migrated += len(points)
        print(f"Migrated {migrated} points.", flush=True)
        if offset is None:
            break

    count = client.count(collection_name=args.target, exact=True).count
    print(f"Collection {args.target!r} now contains {count} points.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
