from datetime import datetime, timezone

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_jti,
    hash_password,
    verify_password,
)
from app.modules.auth.schemas import AuthResponse, LoginRequest, RegisterRequest
from app.modules.users.models import RefreshToken, User

# Verified against when the email is unknown so response time doesn't reveal which emails exist.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _issue_tokens(db: Session, user: User) -> AuthResponse:
    refresh, jti, expires = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, jti_hash=hash_jti(jti), expires_at=expires))
    db.commit()
    return AuthResponse(access_token=create_access_token(user.id, user.role), refresh_token=refresh, user=user)


def register(db: Session, data: RegisterRequest) -> AuthResponse:
    user = User(
        name=data.name.strip(),
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        phone=data.phone,
        role=data.role,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return _issue_tokens(db, user)


def login(db: Session, data: LoginRequest) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    ok = verify_password(data.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return _issue_tokens(db, user)


def refresh(db: Session, refresh_token: str) -> AuthResponse:
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    try:
        payload = decode_token(refresh_token, "refresh")
    except jwt.PyJWTError:
        raise invalid
    record = db.scalar(select(RefreshToken).where(RefreshToken.jti_hash == hash_jti(payload["jti"])))
    if record is None:
        raise invalid
    if record.revoked:
        # Reuse of a rotated token suggests theft: revoke the user's whole token family.
        for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == record.user_id, RefreshToken.revoked.is_(False))):
            t.revoked = True
        db.commit()
        raise invalid
    user = db.get(User, record.user_id)
    if user is None or user.status != "active" or record.expires_at < datetime.now(timezone.utc):
        raise invalid
    record.revoked = True
    return _issue_tokens(db, user)


def logout(db: Session, refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token, "refresh")
    except jwt.PyJWTError:
        return
    record = db.scalar(select(RefreshToken).where(RefreshToken.jti_hash == hash_jti(payload["jti"])))
    if record:
        record.revoked = True
        db.commit()
