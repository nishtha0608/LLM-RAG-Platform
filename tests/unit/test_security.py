"""Unit tests for password hashing and JWT token handling."""

import uuid

import pytest

from app.security import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_produces_verifiable_hash() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_round_trip() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert decode_token(token, TokenType.ACCESS) == user_id


def test_refresh_token_rejected_as_access_token() -> None:
    user_id = uuid.uuid4()
    token = create_refresh_token(user_id)
    with pytest.raises(InvalidTokenError):
        decode_token(token, TokenType.ACCESS)


def test_garbage_token_raises_invalid_token_error() -> None:
    with pytest.raises(InvalidTokenError):
        decode_token("not-a-real-token", TokenType.ACCESS)
