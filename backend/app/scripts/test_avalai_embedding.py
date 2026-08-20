from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import APIError, OpenAI, RateLimitError


def load_environment() -> None:
    for env_file in (Path.cwd() / ".env", Path.cwd() / "backend" / ".env"):
        if env_file.exists():
            load_dotenv(env_file)


def rate_limit_headers(error: RateLimitError) -> dict[str, str]:
    return {
        name: value
        for name, value in error.response.headers.items()
        if "ratelimit" in name.lower() or name.lower() == "retry-after"
    }


def main() -> int:
    load_environment()
    api_key = os.getenv("AVALAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        print("Missing AVALAI_API_KEY (or legacy LLM_API_KEY).")
        return 2

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("AVALAI_BASE_URL", "https://api.avalai.ir/v1"),
        timeout=30,
        max_retries=0,
    )

    try:
        response = client.embeddings.create(
            model=os.getenv("EMBEDDING_MODEL", "gemini-embedding-2"),
            input="title: AvalAI smoke test | text: Verify embedding API availability.",
            dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "768")),
        )
    except RateLimitError as error:
        print("RATE_LIMITED")
        print(rate_limit_headers(error))
        return 1
    except APIError as error:
        print(f"API_ERROR: {error}")
        return 1

    embedding = response.data[0].embedding
    print("SUCCESS")
    print(f"model={response.model}")
    print(f"dimensions={len(embedding)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
