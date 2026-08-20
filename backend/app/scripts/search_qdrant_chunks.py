from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

from app.ingestion.index_documents import (
    DEFAULT_COLLECTION,
    DEFAULT_DIMENSIONS,
    DEFAULT_MODEL,
    DENSE_VECTOR_NAME,
)


def load_environment() -> None:
    candidates = [Path.cwd() / ".env", Path.cwd() / "backend" / ".env"]
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed a query and print the most relevant Qdrant documentation chunks."
    )
    parser.add_argument("query", help="The user's search query")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--collection",
        default=os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION),
    )
    parser.add_argument(
        "--model",
        default=os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL),
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=int(os.getenv("EMBEDDING_DIMENSIONS", str(DEFAULT_DIMENSIONS))),
    )
    parser.add_argument(
        "--expect-source",
        help="Fail unless this source path appears in the returned results.",
    )
    return parser.parse_args()


def main() -> int:
    load_environment()
    args = parse_args()
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")

    api_key = os.getenv("AVALAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("Set AVALAI_API_KEY (or legacy LLM_API_KEY) in backend/.env")

    embedding_client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("AVALAI_BASE_URL", "https://api.avalai.ir/v1"),
        timeout=float(os.getenv("AVALAI_EMBEDDING_TIMEOUT", "60")),
        max_retries=0,
    )
    embedding_response = embedding_client.embeddings.create(
        model=args.model,
        input=args.query,
        dimensions=args.dimensions,
    )
    query_vector = embedding_response.data[0].embedding
    if len(query_vector) != args.dimensions:
        raise RuntimeError(
            f"Expected a {args.dimensions}-dimension query vector, "
            f"received {len(query_vector)} dimensions"
        )

    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        timeout=30,
    )
    if not qdrant.collection_exists(args.collection):
        raise RuntimeError(f"Qdrant collection {args.collection!r} does not exist")

    response = qdrant.query_points(
        collection_name=args.collection,
        query=query_vector,
        using=DENSE_VECTOR_NAME,
        limit=args.limit,
        with_payload=True,
        with_vectors=False,
    )
    points = response.points
    print(f"Query: {args.query}")
    print(f"Found {len(points)} result(s) in {args.collection!r}.\n")

    source_paths: list[str] = []
    for rank, point in enumerate(points, start=1):
        payload = point.payload or {}
        source_path = str(payload.get("source_path", "<missing>"))
        source_paths.append(source_path)
        heading_path = " > ".join(payload.get("heading_path") or [])
        print(f"=== Result {rank} | score={point.score:.6f} ===")
        print(f"Source: {source_path}")
        print(f"Title: {payload.get('document_title', '<missing>')}")
        print(f"Section: {heading_path or '<missing>'}")
        print("Content:")
        print(payload.get("content", "<missing content>"))
        print()

    if args.expect_source:
        if args.expect_source not in source_paths:
            print(
                f"VERIFICATION FAILED: {args.expect_source!r} was not in the top "
                f"{len(points)} results."
            )
            return 1
        rank = source_paths.index(args.expect_source) + 1
        print(f"VERIFICATION PASSED: expected source found at rank {rank}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
