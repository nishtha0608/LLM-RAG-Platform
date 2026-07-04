"""Authentication endpoints: register, login, refresh."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_auth_service
from app.schemas import RefreshRequest, TokenPair, UserCreate, UserLogin, UserRead
from app.services.auth import AuthService, InvalidCredentialsError, UserAlreadyExistsError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate, auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> UserRead:
    try:
        user = await auth_service.register(payload.email, payload.password, payload.full_name)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenPair)
async def login(
    payload: UserLogin, auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> TokenPair:
    try:
        user = await auth_service.authenticate(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    access_token, refresh_token = auth_service.issue_tokens(user)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest, auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> TokenPair:
    try:
        access_token, refresh_token = await auth_service.refresh(payload.refresh_token)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return TokenPair(access_token=access_token, refresh_token=refresh_token)
