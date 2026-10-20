import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.services.exceptions import AuthenticationError, ConflictError

# Verified against when the email is unknown, so login timing doesn't reveal which emails exist.
_DUMMY_HASH = hash_password("airline-dummy-password")


def _issue_tokens(session: AsyncSession, user: User) -> TokenResponse:
    """Adds a refresh-token row to the session. The caller commits."""
    raw_refresh = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            tenant_id=user.tenant_id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return TokenResponse(
        access_token=create_access_token(user.id, user.tenant_id),
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def register(session: AsyncSession, body: RegisterRequest) -> TokenResponse:
    email = body.email.lower()

    existing = await session.scalar(select(User.id).where(User.email == email))
    if existing is not None:
        raise ConflictError("An account with this email already exists")

    hashed = await asyncio.to_thread(hash_password, body.password)

    tenant = Tenant(name=body.tenant_name)
    session.add(tenant)
    await session.flush()

    user = User(tenant_id=tenant.id, email=email, hashed_password=hashed, role="ADMIN")
    session.add(user)
    await session.flush()

    tokens = _issue_tokens(session, user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ConflictError("An account with this email already exists")
    return tokens


async def login(session: AsyncSession, body: LoginRequest) -> TokenResponse:
    email = body.email.lower()
    user = await session.scalar(select(User).where(User.email == email))

    hash_to_check = user.hashed_password if user is not None else _DUMMY_HASH
    valid = await asyncio.to_thread(verify_password, body.password, hash_to_check)
    if user is None or not valid:
        raise AuthenticationError("Invalid email or password")

    tokens = _issue_tokens(session, user)
    await session.commit()
    return tokens


async def refresh(session: AsyncSession, body: RefreshRequest) -> TokenResponse:
    record = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(body.refresh_token))
        .with_for_update()
    )
    if record is None or record.revoked or record.expires_at <= datetime.now(timezone.utc):
        raise AuthenticationError("Invalid or expired refresh token")

    user = await session.get(User, record.user_id)
    if user is None:
        raise AuthenticationError("Invalid or expired refresh token")

    record.revoked = True  # rotation: each refresh token works exactly once
    tokens = _issue_tokens(session, user)
    await session.commit()
    return tokens


async def logout(session: AsyncSession, body: RefreshRequest) -> None:
    record = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(body.refresh_token))
    )
    if record is not None and not record.revoked:
        record.revoked = True
        await session.commit()