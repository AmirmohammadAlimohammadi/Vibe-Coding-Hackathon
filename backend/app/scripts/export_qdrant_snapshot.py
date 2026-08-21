from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from app.ingestion.index_documents import DEFAULT_COLLECTION


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and download a Qdrant collection snapshot."
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("backups"))
    parser.add_argument(
        "--keep-server-snapshot",
        action="store_true",
        help="Leave the generated snapshot on the Qdrant server after download.",
    )
    return parser.parse_args()


def load_environment() -> None:
    for candidate in (Path.cwd() / ".env", Path.cwd() / "backend" / ".env"):
        if candidate.exists():
            load_dotenv(candidate)


def request(url: str, *, method: str = "GET"):
    headers = {"Accept": "application/json"}
    api_key = os.getenv("QDRANT_API_KEY")
    if api_key:
        headers["api-key"] = api_key
    return urlopen(Request(url, method=method, headers=headers), timeout=300)


def main() -> int:
    load_environment()
    args = parse_args()
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
    collection = quote(args.collection, safe="")
    snapshots_url = f"{qdrant_url}/collections/{collection}/snapshots"

    with request(snapshots_url, method="POST") as response:
        payload = json.load(response)
    snapshot_name = Path(str(payload["result"]["name"])).name

    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = args.output_dir / snapshot_name
    checksum = hashlib.sha256()
    snapshot_url = f"{snapshots_url}/{quote(snapshot_name, safe='')}"
    with request(snapshot_url) as response:
        with destination.open("wb") as snapshot_file:
            while chunk := response.read(1024 * 1024):
                snapshot_file.write(chunk)
                checksum.update(chunk)

    if not args.keep_server_snapshot:
        with request(snapshot_url, method="DELETE"):
            pass

    print(f"Snapshot saved to {destination.resolve()}")
    print(f"SHA256: {checksum.hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
