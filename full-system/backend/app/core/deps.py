from collections.abc import Callable

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.modules.ai.llm import LLMClient, get_llm
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Role, User

bearer = HTTPBearer(auto_error=False)


# Reception / nurse accounts may only use these endpoints (check-in work). Everything else is refused here, before
# any route code runs, so no endpoint written for doctors or patients can be reached by this role by mistake.
RECEPTION_PATHS = ("/auth/", "/users/me", "/reception/", "/notifications", "/health")


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AppError(401, "NOT_AUTHENTICATED", "Authentication required. Please log in.")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise AppError(401, "TOKEN_EXPIRED", "Your session has expired. Please log in again.")
    except jwt.PyJWTError:
        raise AppError(401, "INVALID_TOKEN", "Invalid authentication token. Please log in again.")
    user = db.get(User, payload["sub"])
    if user is None or user.token_version != payload.get("tv") or user.role.value != payload.get("role"):
        raise AppError(401, "INVALID_TOKEN", "Your session is no longer valid. Please log in again.")
    if not user.is_active:
        raise AppError(403, "ACCOUNT_INACTIVE", "This account has been deactivated.")
    if user.role == Role.RECEPTION and not request.url.path.startswith(RECEPTION_PATHS):
        raise AppError(403, "FORBIDDEN_ROLE", "Reception accounts can only use the check-in pages.")
    return user


def require_roles(*roles: Role) -> Callable[..., User]:
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError(403, "FORBIDDEN_ROLE", "You do not have permission to perform this action.")
        return user

    return _dep


def get_llm_factory() -> Callable[[], LLMClient]:
    """Returns a factory (not a client) so the LLM is only touched AFTER
    authorization has passed. Overridden in tests."""
    return get_llm
