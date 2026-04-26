import logging
from typing import Callable, Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.services.identity import AuthenticatedUser, resolve_user_from_access_token

logger = logging.getLogger(__name__)

Role = Literal["admin", "user"]
User = AuthenticatedUser
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_user_by_username(username: str) -> User | None:
    from app.services.identity import get_authenticated_user

    return get_authenticated_user(username)


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    user = resolve_user_from_access_token(token)
    logger.info(
        "Authorized request for user '%s' tenant='%s' role='%s'",
        user.username,
        user.tenant_id,
        user.role,
    )
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            logger.warning(
                "User '%s' with role '%s' attempted restricted action. Allowed roles: %s",
                current_user.username,
                current_user.role,
                roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return dependency
