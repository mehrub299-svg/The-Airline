import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semantic_cache import SemanticCache

CACHE_DISTANCE_THRESHOLD = 0.08
LOCK_SECONDS = 120


@dataclass(frozen=True)
class CacheLookup:
    kind: str  # "miss" | "hit" | "in_flight"
    response_text: str | None = None


async def lookup(session: AsyncSession, embedding: list[float]) -> CacheLookup:
    """All functions here take a tenant_session, so RLS scopes them to the current tenant."""
    distance = SemanticCache.query_embedding.cosine_distance(embedding)
    ready = and_(SemanticCache.status == "READY", SemanticCache.response_text.is_not(None))
    live_claim = and_(
        SemanticCache.status == "THINKING_WAIT",
        SemanticCache.locked_until > func.now(),
    )
    row = (
        await session.execute(
            select(SemanticCache.status, SemanticCache.response_text)
            .where(distance < CACHE_DISTANCE_THRESHOLD, or_(ready, live_claim))
            .order_by((SemanticCache.status == "READY").desc(), distance)
            .limit(1)
        )
    ).first()

    if row is None:
        return CacheLookup("miss")
    if row.status == "READY":
        return CacheLookup("hit", row.response_text)
    return CacheLookup("in_flight")


async def claim(
    session: AsyncSession, tenant_id: uuid.UUID, query_text: str, embedding: list[float]
) -> uuid.UUID:
    """Insert the THINKING_WAIT stampede lock. The caller's transaction must commit before the LLM call."""
    await session.execute(
        delete(SemanticCache).where(
            SemanticCache.status == "THINKING_WAIT",
            SemanticCache.locked_until <= func.now(),
        )
    )
    entry = SemanticCache(
        tenant_id=tenant_id,
        query_text=query_text,
        query_embedding=embedding,
        status="THINKING_WAIT",
        locked_until=func.now() + timedelta(seconds=LOCK_SECONDS),
    )
    session.add(entry)
    await session.flush()
    return entry.id


async def mark_ready(session: AsyncSession, cache_id: uuid.UUID, response_text: str) -> None:
    await session.execute(
        update(SemanticCache)
        .where(SemanticCache.id == cache_id, SemanticCache.status == "THINKING_WAIT")
        .values(status="READY", response_text=response_text, locked_until=None)
    )


async def discard(session: AsyncSession, cache_id: uuid.UUID) -> None:
    await session.execute(delete(SemanticCache).where(SemanticCache.id == cache_id))