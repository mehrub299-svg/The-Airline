import logging

import httpx

from app.core.clients import get_http_client, openrouter_headers
from app.core.config import settings
from app.services.exceptions import ServiceUnavailableError

logger = logging.getLogger("airline.embedding")

EMBEDDING_DIM = 1536
_BATCH_SIZE = 64


async def _embed_batch(texts: list[str]) -> list[list[float]]:
    if not settings.OPENROUTER_API_KEY:
        raise ServiceUnavailableError("Embedding provider is not configured")

    try:
        response = await get_http_client().post(
            "/embeddings",
            headers=openrouter_headers(),
            json={"model": settings.OPENROUTER_EMBEDDING_MODEL, "input": texts},
        )
        response.raise_for_status()
        items = sorted(response.json()["data"], key=lambda item: item["index"])
        vectors = [item["embedding"] for item in items]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        logger.error("Embedding request failed: %s", exc)
        raise ServiceUnavailableError("Embedding service unavailable")

    if len(vectors) != len(texts) or any(len(v) != EMBEDDING_DIM for v in vectors):
        logger.error("Embedding response had unexpected shape or dimensions")
        raise ServiceUnavailableError("Embedding service returned unexpected data")
    return vectors


async def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        vectors.extend(await _embed_batch(texts[start : start + _BATCH_SIZE]))
    return vectors


async def embed_query(text: str) -> list[float]:
    return (await embed_texts([text]))[0]