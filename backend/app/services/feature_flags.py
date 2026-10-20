import asyncio
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.feature_flag import FeatureFlag
from app.services.exceptions import ServiceUnavailableError

MASTER_SWITCH = "global_ai_master_switch"
RAG_V2 = "rag_v2"

_TTL_SECONDS = 5.0


@dataclass(frozen=True)
class _Flag:
    enabled: bool
    overrides: dict[str, bool]


_cache: dict[str, _Flag] = {}
_cache_expires_at = 0.0
_refresh_lock = asyncio.Lock()


async def _get_flags() -> dict[str, _Flag]:
    """All flags in one query, cached per process for a few seconds so hot paths cost ~0 ms."""
    global _cache, _cache_expires_at
    if time.monotonic() < _cache_expires_at:
        return _cache
    async with _refresh_lock:
        if time.monotonic() < _cache_expires_at:
            return _cache
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(select(FeatureFlag))).scalars().all()
        _cache = {
            row.flag_key: _Flag(row.is_enabled_globally, dict(row.tenant_overrides or {}))
            for row in rows
        }
        _cache_expires_at = time.monotonic() + _TTL_SECONDS
        return _cache


async def is_enabled(flag_key: str, tenant_id: uuid.UUID) -> bool:
    """Tenant override wins; otherwise the global value. Unknown flags are off."""
    flag = (await _get_flags()).get(flag_key)
    if flag is None:
        return False
    override = flag.overrides.get(str(tenant_id))
    return flag.enabled if override is None else bool(override)


async def require_ai_enabled() -> None:
    """Global master switch (no per-tenant override). Off or missing -> 503 before any LLM call."""
    flag = (await _get_flags()).get(MASTER_SWITCH)
    if flag is None or not flag.enabled:
        raise ServiceUnavailableError("Service maintenance")


async def effective_flags(tenant_id: uuid.UUID) -> dict[str, bool]:
    flags = await _get_flags()
    result: dict[str, bool] = {}
    for key, flag in flags.items():
        if key == MASTER_SWITCH:
            result[key] = flag.enabled
        else:
            override = flag.overrides.get(str(tenant_id))
            result[key] = flag.enabled if override is None else bool(override)
    return result