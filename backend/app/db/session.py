import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.engine import engine

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def tenant_session(tenant_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """Tenant-scoped session with RLS enforced.

    One transaction for the whole block: SET LOCAL ROLE + tenant id apply until it ends, then the
    pooled connection resets cleanly. The transaction commits when the block exits normally and
    rolls back on any exception. Inside the block use flush(), never commit().
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("SET LOCAL ROLE tenant_user"))
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            yield session