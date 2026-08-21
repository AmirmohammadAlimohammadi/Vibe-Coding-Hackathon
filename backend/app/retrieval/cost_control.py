from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError


logger = logging.getLogger(__name__)


ACQUIRE_SCRIPT = """
local minute_count = tonumber(redis.call('GET', KEYS[1]) or '0')
if minute_count >= tonumber(ARGV[1]) then
    return {-1, redis.call('TTL', KEYS[1])}
end

local daily_count = tonumber(redis.call('GET', KEYS[2]) or '0')
if daily_count >= tonumber(ARGV[2]) then
    return {-2, redis.call('TTL', KEYS[2])}
end

local token_count = tonumber(redis.call('GET', KEYS[3]) or '0')
if token_count + tonumber(ARGV[10]) > tonumber(ARGV[3]) then
    return {-3, redis.call('TTL', KEYS[3])}
end

local concurrent = tonumber(redis.call('GET', KEYS[4]) or '0')
if concurrent >= tonumber(ARGV[4]) then
    return {-4, 1}
end

local global_minute = tonumber(redis.call('GET', KEYS[5]) or '0')
if global_minute >= tonumber(ARGV[7]) then
    return {-5, redis.call('TTL', KEYS[5])}
end

local global_daily = tonumber(redis.call('GET', KEYS[6]) or '0')
if global_daily >= tonumber(ARGV[8]) then
    return {-6, redis.call('TTL', KEYS[6])}
end

local global_tokens = tonumber(redis.call('GET', KEYS[7]) or '0')
if global_tokens + tonumber(ARGV[10]) > tonumber(ARGV[9]) then
    return {-7, redis.call('TTL', KEYS[7])}
end

minute_count = redis.call('INCR', KEYS[1])
if minute_count == 1 then redis.call('EXPIRE', KEYS[1], 60) end
daily_count = redis.call('INCR', KEYS[2])
if daily_count == 1 then redis.call('EXPIRE', KEYS[2], ARGV[5]) end
global_minute = redis.call('INCR', KEYS[5])
if global_minute == 1 then redis.call('EXPIRE', KEYS[5], 60) end
global_daily = redis.call('INCR', KEYS[6])
if global_daily == 1 then redis.call('EXPIRE', KEYS[6], ARGV[5]) end
concurrent = redis.call('INCR', KEYS[4])
if concurrent == 1 then redis.call('EXPIRE', KEYS[4], ARGV[6]) end
if tonumber(ARGV[10]) > 0 then
    redis.call('INCRBY', KEYS[3], ARGV[10])
    redis.call('EXPIRE', KEYS[3], ARGV[5])
    redis.call('INCRBY', KEYS[7], ARGV[10])
    redis.call('EXPIRE', KEYS[7], ARGV[5])
end

return {1, 0}
"""


RELEASE_SCRIPT = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
if current <= 1 then
    redis.call('DEL', KEYS[1])
else
    redis.call('DECR', KEYS[1])
end
return 1
"""


class RagLimitError(RuntimeError):
    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = max(1, retry_after)


class RagRateLimitError(RagLimitError):
    pass


class RagBudgetExceededError(RagLimitError):
    pass


@dataclass(frozen=True)
class RagLease:
    concurrency_key: str | None
    user_token_key: str | None
    global_token_key: str | None
    reserved_tokens: int
    day_ttl: int


class RagCostGuard:
    def __init__(self) -> None:
        self.enabled = os.getenv("RAG_COST_GUARD_ENABLED", "true").lower() == "true"
        self.requests_per_minute = int(
            os.getenv("RAG_REQUESTS_PER_MINUTE_PER_USER", "12")
        )
        self.requests_per_day = int(os.getenv("RAG_REQUESTS_PER_DAY_PER_USER", "200"))
        self.tokens_per_day = int(os.getenv("RAG_TOKENS_PER_DAY_PER_USER", "100000"))
        self.max_concurrency = int(os.getenv("RAG_MAX_CONCURRENT_PER_USER", "2"))
        self.global_requests_per_minute = int(
            os.getenv("RAG_REQUESTS_PER_MINUTE_GLOBAL", "60")
        )
        self.global_requests_per_day = int(
            os.getenv("RAG_REQUESTS_PER_DAY_GLOBAL", "2000")
        )
        self.global_tokens_per_day = int(
            os.getenv("RAG_TOKENS_PER_DAY_GLOBAL", "500000")
        )
        self.lease_seconds = int(os.getenv("RAG_CONCURRENCY_LEASE_SECONDS", "900"))
        self.estimated_tokens_per_request = int(
            os.getenv("RAG_ESTIMATED_TOKENS_PER_REQUEST", "7000")
        )
        self.redis = Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

    @staticmethod
    def _day() -> tuple[str, int]:
        now = datetime.now(UTC)
        tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), UTC)
        return now.date().isoformat(), max(60, int((tomorrow - now).total_seconds()))

    def acquire(self, user_id: str) -> RagLease:
        if not self.enabled:
            return RagLease(None, None, None, 0, 0)
        day, day_ttl = self._day()
        base = f"rag:limit:{user_id}"
        concurrency_key = f"{base}:concurrent"
        user_token_key = f"{base}:tokens:{day}"
        global_token_key = f"rag:limit:global:tokens:{day}"
        try:
            result = self.redis.eval(
                ACQUIRE_SCRIPT,
                7,
                f"{base}:minute:{int(time.time() // 60)}",
                f"{base}:requests:{day}",
                user_token_key,
                concurrency_key,
                f"rag:limit:global:minute:{int(time.time() // 60)}",
                f"rag:limit:global:requests:{day}",
                global_token_key,
                self.requests_per_minute,
                self.requests_per_day,
                self.tokens_per_day,
                self.max_concurrency,
                day_ttl,
                self.lease_seconds,
                self.global_requests_per_minute,
                self.global_requests_per_day,
                self.global_tokens_per_day,
                self.estimated_tokens_per_request,
            )
        except RedisError:
            logger.warning("RAG cost guard unavailable; failing open", exc_info=True)
            return RagLease(None, None, None, 0, 0)

        status, retry_after = int(result[0]), max(1, int(result[1]))
        if status == -1:
            raise RagRateLimitError("Too many chatbot requests. Please retry shortly.", retry_after)
        if status == -2:
            raise RagBudgetExceededError(
                "Daily chatbot request budget reached. Please try again tomorrow.",
                retry_after,
            )
        if status == -3:
            raise RagBudgetExceededError(
                "Daily chatbot token budget reached. Please try again tomorrow.",
                retry_after,
            )
        if status == -4:
            raise RagRateLimitError(
                "Too many chatbot requests are running. Please retry shortly.",
                retry_after,
            )
        if status == -5:
            raise RagRateLimitError(
                "The chatbot is busy. Please retry shortly.",
                retry_after,
            )
        if status in {-6, -7}:
            raise RagBudgetExceededError(
                "The chatbot's daily service budget has been reached.",
                retry_after,
            )
        return RagLease(
            concurrency_key,
            user_token_key,
            global_token_key,
            self.estimated_tokens_per_request,
            day_ttl,
        )

    def release(self, lease: RagLease) -> None:
        if lease.concurrency_key is None:
            return
        try:
            self.redis.eval(RELEASE_SCRIPT, 1, lease.concurrency_key)
        except RedisError:
            logger.warning("Failed to release RAG concurrency lease", exc_info=True)

    def settle_tokens(self, lease: RagLease, total_tokens: int) -> None:
        if (
            not self.enabled
            or lease.user_token_key is None
            or lease.global_token_key is None
        ):
            return
        adjustment = max(0, total_tokens) - lease.reserved_tokens
        try:
            with self.redis.pipeline(transaction=True) as pipeline:
                pipeline.incrby(lease.user_token_key, adjustment)
                pipeline.expire(lease.user_token_key, lease.day_ttl)
                pipeline.incrby(lease.global_token_key, adjustment)
                pipeline.expire(lease.global_token_key, lease.day_ttl)
                pipeline.execute()
        except RedisError:
            logger.warning("Failed to settle RAG token reservation", exc_info=True)


@lru_cache(maxsize=1)
def get_rag_cost_guard() -> RagCostGuard:
    return RagCostGuard()
