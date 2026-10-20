import uuid
from collections.abc import AsyncIterator

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal, tenant_session
from app.models.user import User
from app.services.exceptions import AuthenticationError

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Plain session (owner role). Only for non-RLS tables: tenants, users, refresh_tokens,
    idempotency_keys, feature_flags. Services call commit() themselves."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None:
        raise AuthenticationError("Missing bearer token")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
        tenant_id = uuid.UUID(payload["tid"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AuthenticationError("Invalid or expired token")

    # Short-lived session: the connection goes back to the pool before the endpoint runs.
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)

    if user is None or user.tenant_id != tenant_id:
        raise AuthenticationError("Invalid or expired token")
    return user


async def get_tenant_db(
    current_user: User = Depends(get_current_user),
) -> AsyncIterator[AsyncSession]:
    """RLS-enforced session for simple endpoints (list, delete). The transaction commits when the
    request finishes. Endpoints using it must flush(), never commit()."""
    async with tenant_session(current_user.tenant_id) as session:
        yield session