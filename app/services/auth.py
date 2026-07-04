"""Authentication service: registration, login, and token refresh."""

from app.models import User
from app.repositories import UserRepository
from app.security import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class UserAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    async def register(self, email: str, password: str, full_name: str | None) -> User:
        existing = await self._users.get_by_email(email)
        if existing is not None:
            raise UserAlreadyExistsError(f"A user with email {email} already exists")

        user = User(email=email, hashed_password=hash_password(password), full_name=full_name)
        return await self._users.create(user)

    async def authenticate(self, email: str, password: str) -> User:
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password")
        if not user.is_active:
            raise InvalidCredentialsError("Account is disabled")
        return user

    def issue_tokens(self, user: User) -> tuple[str, str]:
        return create_access_token(user.id), create_refresh_token(user.id)

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        try:
            user_id = decode_token(refresh_token, TokenType.REFRESH)
        except InvalidTokenError as exc:
            raise InvalidCredentialsError(str(exc)) from exc

        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidCredentialsError("User no longer exists or is disabled")
        return self.issue_tokens(user)
