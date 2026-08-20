from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.email import EmailDeliveryError, get_email_sender
from app.auth.models import User
from app.auth.otp import OtpRateLimitError, OtpVerificationResult, get_otp_store
from app.auth.repository import (
    get_or_create_verified_user,
    normalize_email,
    update_user_expertise_level,
)
from app.auth.schemas import (
    AccessTokenResponse,
    EmailCodeRequest,
    EmailCodeSentResponse,
    EmailCodeVerifyRequest,
    UserPreferencesUpdateRequest,
    UserResponse,
)
from app.auth.tokens import get_access_token_service
from app.database import get_database_session


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/email/request",
    response_model=EmailCodeSentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_email_code(
    payload: EmailCodeRequest,
    request: Request,
) -> EmailCodeSentResponse:
    email = normalize_email(str(payload.email))
    client_ip = request.client.host if request.client else "unknown"
    try:
        otp_store = get_otp_store()
        issued = otp_store.issue(email, client_ip)
    except OtpRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting another code",
            headers={"Retry-After": str(error.retry_after)},
        ) from error
    except Exception as error:
        logger.exception("Unable to store an OTP")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        ) from error

    try:
        get_email_sender().send(email, issued.code, issued.expires_in)
    except (EmailDeliveryError, RuntimeError, ValueError) as error:
        otp_store.revoke(email)
        logger.exception("Unable to deliver an OTP email")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to send the login code",
        ) from error

    return EmailCodeSentResponse(
        message="A login code was sent to the email address",
        expires_in=issued.expires_in,
        retry_after=issued.retry_after,
    )


@router.post("/email/verify", response_model=AccessTokenResponse)
def verify_email_code(
    payload: EmailCodeVerifyRequest,
    session: Session = Depends(get_database_session),
) -> AccessTokenResponse:
    email = normalize_email(str(payload.email))
    try:
        token_service = get_access_token_service()
        verification = get_otp_store().verify(email, payload.code)
    except Exception as error:
        logger.exception("Unable to verify an OTP")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        ) from error
    if verification != OtpVerificationResult.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The code is invalid or expired",
        )

    user = get_or_create_verified_user(session, email)
    return AccessTokenResponse(
        access_token=token_service.create(user.id),
        expires_in=token_service.expires_seconds,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
def update_current_user_preferences(
    payload: UserPreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_database_session),
) -> UserResponse:
    user = update_user_expertise_level(
        session,
        current_user,
        payload.expertise_level,
    )
    return UserResponse.model_validate(user)
