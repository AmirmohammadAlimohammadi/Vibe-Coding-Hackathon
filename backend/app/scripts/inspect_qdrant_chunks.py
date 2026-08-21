from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from app.ingestion.index_documents import DEFAULT_COLLECTION
from app.qdrant import create_qdrant_client


def load_environment() -> None:
    candidates = [Path.cwd() / ".env", Path.cwd() / "backend" / ".env"]
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print chunks stored in the Qdrant documentation collection."
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--collection",
        default=os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION),
    )
    return parser.parse_args()


def main() -> int:
    load_environment()
    args = parse_args()
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")

    client = create_qdrant_client(timeout=30)
    if not client.collection_exists(args.collection):
        raise RuntimeError(f"Qdrant collection {args.collection!r} does not exist")

    points, _ = client.scroll(
        collection_name=args.collection,
        limit=args.limit,
        with_payload=True,
        with_vectors=False,
    )
    print(f"Found {len(points)} chunk(s) in {args.collection!r}.\n")

    for index, point in enumerate(points, start=1):
        payload = point.payload or {}
        metadata = {key: value for key, value in payload.items() if key != "content"}
        print(f"=== Chunk {index} ===")
        print(f"Point ID: {point.id}")
        print("Metadata:")
        print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
        print("Content:")
        print(payload.get("content", "<missing content>"))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
