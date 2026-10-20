from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk


async def retrieve_chunks(session: AsyncSession, query_embedding: list[float], top_k: int) -> list[str]:
    """Nearest chunks by cosine distance. Runs on a tenant_session, so RLS limits it to one tenant."""
    result = await session.scalars(
        select(Chunk.content)
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    return list(result.all())