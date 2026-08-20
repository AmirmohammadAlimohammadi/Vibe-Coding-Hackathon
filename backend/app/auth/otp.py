from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from redis import Redis

from app.auth.repository import normalize_email


RESERVE_OTP_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 1 then
    return {-1, redis.call('TTL', KEYS[1])}
end

local email_count = redis.call('INCR', KEYS[2])
if email_count == 1 then
    redis.call('EXPIRE', KEYS[2], ARGV[1])
end
if email_count > tonumber(ARGV[2]) then
    return {-2, redis.call('TTL', KEYS[2])}
end

local ip_count = redis.call('INCR', KEYS[3])
if ip_count == 1 then
    redis.call('EXPIRE', KEYS[3], ARGV[1])
end
if ip_count > tonumber(ARGV[3]) then
    return {-2, redis.call('TTL', KEYS[3])}
end

redis.call('SET', KEYS[1], '1', 'EX', ARGV[4])
return {1, tonumber(ARGV[4])}
"""


VERIFY_OTP_SCRIPT = """
local expected = redis.call('HGET', KEYS[1], 'digest')
if not expected then
    return {-1, 0}
end

local attempts = tonumber(redis.call('HGET', KEYS[1], 'attempts') or '0')
local max_attempts = tonumber(ARGV[2])
if attempts >= max_attempts then
    redis.call('DEL', KEYS[1])
    return {-2, 0}
end

if expected == ARGV[1] then
    redis.call('DEL', KEYS[1])
    return {1, 0}
end

attempts = attempts + 1
if attempts >= max_attempts then
    redis.call('DEL', KEYS[1])
    return {0, 0}
end
redis.call('HSET', KEYS[1], 'attempts', attempts)
return {0, max_attempts - attempts}
"""


class OtpRateLimitError(RuntimeError):
    def __init__(self, retry_after: int) -> None:
        super().__init__("OTP requests are temporarily limited")
        self.retry_after = max(retry_after, 1)


class OtpVerificationResult(str, Enum):
    VERIFIED = "verified"
    INVALID = "invalid"
    EXPIRED = "expired"
    LOCKED = "locked"


@dataclass(frozen=True)
class IssuedOtp:
    code: str
    expires_in: int
    retry_after: int


class OtpStore:
    def __init__(self) -> None:
        self.redis = Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
        self.hash_secret = self._required_secret("OTP_HASH_SECRET")
        self.ttl_seconds = int(os.getenv("OTP_TTL_SECONDS", "300"))
        self.cooldown_seconds = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60"))
        self.max_attempts = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
        self.email_requests_per_hour = int(os.getenv("OTP_EMAIL_REQUESTS_PER_HOUR", "5"))
        self.ip_requests_per_hour = int(os.getenv("OTP_IP_REQUESTS_PER_HOUR", "30"))

    @staticmethod
    def _required_secret(name: str) -> bytes:
        value = os.getenv(name, "")
        if len(value) < 32 or value.startswith("replace-"):
            raise RuntimeError(f"{name} must contain at least 32 characters")
        return value.encode("utf-8")

    @staticmethod
    def _identity_digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _email_digest(self, email: str) -> str:
        return self._identity_digest(normalize_email(email))

    def _otp_key(self, email: str) -> str:
        return f"auth:otp:code:{self._email_digest(email)}"

    def _cooldown_key(self, email: str) -> str:
        return f"auth:otp:cooldown:{self._email_digest(email)}"

    def _code_digest(self, email: str, code: str) -> str:
        message = f"{normalize_email(email)}:{code}".encode("utf-8")
        return hmac.new(self.hash_secret, message, hashlib.sha256).hexdigest()

    def issue(self, email: str, client_ip: str) -> IssuedOtp:
        email_digest = self._email_digest(email)
        ip_digest = self._identity_digest(client_ip)
        result = self.redis.eval(
            RESERVE_OTP_SCRIPT,
            3,
            self._cooldown_key(email),
            f"auth:otp:hour:email:{email_digest}",
            f"auth:otp:hour:ip:{ip_digest}",
            3600,
            self.email_requests_per_hour,
            self.ip_requests_per_hour,
            self.cooldown_seconds,
        )
        status, retry_after = int(result[0]), int(result[1])
        if status < 0:
            raise OtpRateLimitError(retry_after)

        code = f"{secrets.randbelow(1_000_000):06d}"
        otp_key = self._otp_key(email)
        with self.redis.pipeline(transaction=True) as pipeline:
            pipeline.hset(
                otp_key,
                mapping={"digest": self._code_digest(email, code), "attempts": 0},
            )
            pipeline.expire(otp_key, self.ttl_seconds)
            pipeline.execute()
        return IssuedOtp(
            code=code,
            expires_in=self.ttl_seconds,
            retry_after=self.cooldown_seconds,
        )

    def verify(self, email: str, code: str) -> OtpVerificationResult:
        result = self.redis.eval(
            VERIFY_OTP_SCRIPT,
            1,
            self._otp_key(email),
            self._code_digest(email, code),
            self.max_attempts,
        )
        status = int(result[0])
        if status == 1:
            return OtpVerificationResult.VERIFIED
        if status == -1:
            return OtpVerificationResult.EXPIRED
        if status == -2:
            return OtpVerificationResult.LOCKED
        return OtpVerificationResult.INVALID

    def revoke(self, email: str) -> None:
        self.redis.delete(self._otp_key(email), self._cooldown_key(email))


@lru_cache(maxsize=1)
def get_otp_store() -> OtpStore:
    return OtpStore()
