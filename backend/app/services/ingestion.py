from sqlalchemy import delete

from app.models.semantic_cache import SemanticCache
import uuid
from pathlib import PurePath

from app.db.session import tenant_session
from app.models.document import Chunk, Document
from app.schemas.document import DocumentUploadResponse
from app.services.chunking import chunk_text
from app.services.embedding import embed_texts
from app.services.exceptions import BadRequestError
from app.services.extraction import detect_content_type, extract_text

MAX_CHUNKS = 300


async def ingest_document(tenant_id: uuid.UUID, filename: str, data: bytes) -> DocumentUploadResponse:
    content_type = detect_content_type(filename)
    text = await extract_text(data, content_type)

    chunks = chunk_text(text)
    if not chunks:
        raise BadRequestError("No extractable text found")
    if len(chunks) > MAX_CHUNKS:
        raise BadRequestError(f"Document is too large (limit is {MAX_CHUNKS} chunks, about 300,000 characters)")

    # Slow network call happens BEFORE any database transaction is opened.
    vectors = await embed_texts(chunks)

    safe_name = PurePath(filename).name[:512]
    async with tenant_session(tenant_id) as session:
        document = Document(tenant_id=tenant_id, filename=safe_name, content_type=content_type)
        session.add(document)
        await session.flush()

        session.add_all(
            [
                Chunk(
                    tenant_id=tenant_id,
                    document_id=document.id,
                    chunk_index=index,
                    content=content,
                    embedding=vector,
                )
                for index, (content, vector) in enumerate(zip(chunks, vectors))
            ]
        )
        await session.flush()
         # New content makes previously cached answers stale (RLS limits this to the tenant).
        await session.execute(delete(SemanticCache))
        await session.refresh(document)

        response = DocumentUploadResponse(
            id=document.id,
            filename=document.filename,
            content_type=document.content_type,
            created_at=document.created_at,
            chunk_count=len(chunks),
        )
    # the transaction is committed here, when the block exits
    return response