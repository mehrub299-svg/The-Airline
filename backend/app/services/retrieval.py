import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Chunk


async def retrieve_chunks(
    session: AsyncSession,
    query_embedding: list[float],
    top_k: int,
    document_ids: list[uuid.UUID] | None = None,
) -> list[str]:
    """Nearest chunks by cosine distance, optionally limited to some documents.
    Runs on a tenant_session, so RLS limits it to one tenant either way."""
    statement = select(Chunk.content)
    if document_ids:
        statement = statement.where(Chunk.document_id.in_(document_ids))
    statement = statement.order_by(Chunk.embedding.cosine_distance(query_embedding)).limit(top_k)

    result = await session.scalars(statement)
    return list(result.all())