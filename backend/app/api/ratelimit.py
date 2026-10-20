import math
import uuid

from sqlalchemy import select, text

from app.db.session import AsyncSessionLocal
from app.models.tenant import Tenant
from app.services.exceptions import RateLimitError

BUCKET_CAPACITY = 5.0
BUCKET_REFILL_PER_SECOND = 0.1  # 1 coin per 10 s
CHAT_LOCK_SECONDS = 120  # safety expiry for chat_in_process_until if a worker dies mid-stream

_REFILLED = (
    f"LEAST({BUCKET_CAPACITY}::float8, token_bucket_coins + "
    f"{BUCKET_REFILL_PER_SECOND}::float8 * "
    f"EXTRACT(EPOCH FROM (now() - token_bucket_last_refill))::float8)"
)

# One atomic statement: refill, check coins >= 1, check no stream in flight, spend 1 coin, take the stream lock.
_ACQUIRE_SQL = text(
    f"""
    UPDATE tenants
    SET token_bucket_coins = {_REFILLED} - 1.0,
        token_bucket_last_refill = now(),
        chat_in_process_until = now() + interval '{CHAT_LOCK_SECONDS} seconds'
    WHERE id = :tid
      AND (chat_in_process_until IS NULL OR chat_in_process_until <= now())
      AND {_REFILLED} >= 1.0
    RETURNING token_bucket_coins
    """
)

_STATE_SQL = text(
    f"""
    SELECT (chat_in_process_until IS NOT NULL AND chat_in_process_until > now()) AS busy,
           GREATEST(0, EXTRACT(EPOCH FROM (chat_in_process_until - now())))::float8 AS busy_seconds,
           {_REFILLED} AS coins_now
    FROM tenants
    WHERE id = :tid
    """
)


async def acquire_chat_slot(tenant_id: uuid.UUID) -> None:
    """Door 1 (front door, before the semantic cache).

    On success the tenant has spent 1 coin and holds the chat lock. The caller MUST later clear it:
    the streaming `finally:` block (Phase 5) or release_chat_slot() on any early exit.
    """
    async with AsyncSessionLocal() as session:
        spent = await session.scalar(_ACQUIRE_SQL, {"tid": tenant_id})
        if spent is not None:
            await session.commit()
            return
        state = (await session.execute(_STATE_SQL, {"tid": tenant_id})).one_or_none()

    if state is None:
        raise RateLimitError("Unknown workspace")
    if state.busy:
        raise RateLimitError(
            "A response is already being generated for your workspace",
            retry_after=max(1, math.ceil(state.busy_seconds)),
        )
    wait = math.ceil((1.0 - state.coins_now) / BUCKET_REFILL_PER_SECOND)
    raise RateLimitError("Rate limit exceeded. Please slow down.", retry_after=max(1, wait))


async def release_chat_slot(tenant_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("UPDATE tenants SET chat_in_process_until = NULL WHERE id = :tid"),
            {"tid": tenant_id},
        )
        await session.commit()


async def check_monthly_quota(tenant_id: uuid.UUID) -> None:
    """Door 2 (after a cache miss, before OpenRouter)."""
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(Tenant.monthly_tokens_used, Tenant.monthly_token_limit).where(
                    Tenant.id == tenant_id
                )
            )
        ).one_or_none()
    if row is None or row.monthly_tokens_used >= row.monthly_token_limit:
        raise RateLimitError("Monthly token limit reached. Upgrade to PRO to continue.")