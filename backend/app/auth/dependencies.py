from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.repository import get_user_by_id
from app.auth.tokens import TokenError, get_access_token_service
from app.database import get_database_session


bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    scheme_name="AccessToken",
    description=(
        "Paste the access_token returned by POST /auth/email/verify. "
        "Swagger automatically adds the Bearer prefix."
    ),
    auto_error=False,
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_database_session),
) -> User:
    authentication_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise authentication_error
    try:
        user_id = get_access_token_service().decode_subject(credentials.credentials)
    except (TokenError, RuntimeError) as error:
        raise authentication_error from error

    user = get_user_by_id(session, user_id)
    if user is None:
        raise authentication_error
    return user
