import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import AsyncSessionLocal
from app.models.idempotency import IdempotencyKey
from app.services.exceptions import ConflictError

LOCK_SECONDS = 60
_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class IdempotencyOutcome:
    replay: bool
    response_code: int | None = None
    response_body: dict[str, Any] | None = None


async def begin(tenant_id: uuid.UUID, key: str, endpoint: str) -> IdempotencyOutcome:
    """Claim an idempotency key.

    replay=False -> caller owns the key and must run the work, then call complete() (or release()).
    replay=True  -> the work already finished; return the saved response_code/response_body as-is.
    Raises ConflictError (409) while another request holds a live IN_PROCESS lock.
    Each step uses its own short transaction so other requests see the lock immediately.
    """
    lock_until = func.now() + timedelta(seconds=LOCK_SECONDS)

    for _ in range(_MAX_ATTEMPTS):
        async with AsyncSessionLocal() as session:
            inserted = await session.scalar(
                pg_insert(IdempotencyKey)
                .values(
                    tenant_id=tenant_id,
                    key=key,
                    endpoint=endpoint,
                    status="IN_PROCESS",
                    locked_until=lock_until,
                )
                .on_conflict_do_nothing(index_elements=["tenant_id", "key"])
                .returning(IdempotencyKey.key)
            )
            if inserted is not None:
                await session.commit()
                return IdempotencyOutcome(replay=False)

            result = await session.execute(
                select(
                    IdempotencyKey,
                    (IdempotencyKey.locked_until > func.now()).label("lock_alive"),
                ).where(IdempotencyKey.tenant_id == tenant_id, IdempotencyKey.key == key)
            )
            found = result.one_or_none()
            if found is None:
                continue  # row was released between the two statements; try the insert again
            row, lock_alive = found

            if row.endpoint != endpoint:
                raise ConflictError("Idempotency-Key was already used for a different endpoint")
            if row.status == "COMPLETED":
                return IdempotencyOutcome(True, row.response_code, row.response_body)
            if lock_alive:
                raise ConflictError("A request with this Idempotency-Key is already in progress")

            # Zombie lock: IN_PROCESS but expired. The WHERE guard makes the takeover atomic.
            took_over = await session.scalar(
                update(IdempotencyKey)
                .where(
                    IdempotencyKey.tenant_id == tenant_id,
                    IdempotencyKey.key == key,
                    IdempotencyKey.status == "IN_PROCESS",
                    IdempotencyKey.locked_until <= func.now(),
                )
                .values(locked_until=lock_until)
                .returning(IdempotencyKey.key)
            )
            if took_over is not None:
                await session.commit()
                return IdempotencyOutcome(replay=False)
            # lost a race with another takeover or completion: loop and re-evaluate

    raise ConflictError("A request with this Idempotency-Key is already in progress")


async def complete(
    tenant_id: uuid.UUID, key: str, response_code: int, response_body: dict[str, Any]
) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(IdempotencyKey)
            .where(IdempotencyKey.tenant_id == tenant_id, IdempotencyKey.key == key)
            .values(
                status="COMPLETED",
                response_code=response_code,
                response_body=response_body,
                locked_until=func.now(),
            )
        )
        await session.commit()


async def release(tenant_id: uuid.UUID, key: str) -> None:
    """Drop an unfinished claim after a failure so the client can retry immediately."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(IdempotencyKey).where(
                IdempotencyKey.tenant_id == tenant_id,
                IdempotencyKey.key == key,
                IdempotencyKey.status == "IN_PROCESS",
            )
        )
        await session.commit()