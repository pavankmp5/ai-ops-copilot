from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.auth import User, get_current_user, require_roles
from app.services.identity import (
    CreateUserRequest,
    RegistrationRequest,
    TokenBundle,
    authenticate_user,
    create_user_by_admin,
    refresh_access_token,
    register_user,
    revoke_refresh_token,
)
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginResponse(BaseModel):
    tokens: TokenBundle
    user: User


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/token", response_model=LoginResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user, tokens = authenticate_user(form_data.username, form_data.password)
    return LoginResponse(tokens=tokens, user=user)


@router.post("/refresh", response_model=LoginResponse)
def refresh_token(request: RefreshRequest):
    user, tokens = refresh_access_token(request.refresh_token)
    return LoginResponse(tokens=tokens, user=user)


@router.post("/logout")
def logout(request: LogoutRequest, current_user: User = Depends(get_current_user)):
    revoke_refresh_token(request.refresh_token, actor_username=current_user.username)
    return {"message": f"User '{current_user.username}' logged out successfully."}


@router.post("/register", response_model=User)
def register(request: RegistrationRequest):
    return register_user(
        RegistrationRequest(
            username=request.username,
            password=request.password,
            tenant_id=request.tenant_id,
            role="viewer",
        )
    )


@router.post("/users", response_model=User)
def create_user(request: CreateUserRequest, current_user: User = Depends(require_roles("admin"))):
    return create_user_by_admin(request, current_user)


@router.get("/me", response_model=User)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
