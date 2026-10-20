import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("airline.clients")

_http_client: httpx.AsyncClient | None = None
_background_tasks: set[asyncio.Task] = set()


def init_http_client() -> httpx.AsyncClient:
    """Create the shared AsyncClient once. Called from the FastAPI lifespan."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=settings.OPENROUTER_BASE_URL,
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0),
        )
    return _http_client


async def close_http_client() -> None:
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


def get_http_client() -> httpx.AsyncClient:
    if _http_client is None:
        raise RuntimeError("HTTP client is not initialised; the app lifespan has not started.")
    return _http_client


def openrouter_headers() -> dict[str, str]:
    # Sent per request (not as a client default) so the key is never attached to n8n calls.
    return {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


async def _post_n8n(event: str, payload: dict[str, Any]) -> None:
    try:
        client = get_http_client()
        await client.post(
            settings.N8N_WEBHOOK_URL,
            json={"event": event, "data": payload},
            timeout=5.0,
        )
    except Exception as exc:  # never let a webhook failure affect a request
        logger.warning("n8n webhook failed for event %s: %s", event, exc)


def notify_n8n(event: str, payload: dict[str, Any]) -> None:
    """Fire-and-forget. No-op when N8N_WEBHOOK_URL is empty."""
    if not settings.N8N_WEBHOOK_URL:
        return
    task = asyncio.create_task(_post_n8n(event, payload))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)