import uuid
from app.models.semantic_cache import SemanticCache
from fastapi import APIRouter, Depends, File, Header, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_tenant_db
from app.models.document import Chunk, Document
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services import idempotency
from app.services.exceptions import NotFoundError, PayloadTooLargeError
from app.services.extraction import MAX_UPLOAD_BYTES
from app.services.ingestion import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])

_ENDPOINT = "POST /documents"


@router.post("", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
):
    tenant_id = current_user.tenant_id
    key = str(idempotency_key)

    outcome = await idempotency.begin(tenant_id, key, _ENDPOINT)
    if outcome.replay:
        return JSONResponse(status_code=outcome.response_code, content=outcome.response_body)

    try:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise PayloadTooLargeError(f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")

        result = await ingest_document(tenant_id, file.filename or "", data)
        await idempotency.complete(tenant_id, key, 201, result.model_dump(mode="json"))
    except Exception:
        await idempotency.release(tenant_id, key)
        raise
    return result


@router.get("", response_model=list[DocumentResponse])
async def list_documents(session: AsyncSession = Depends(get_tenant_db)):
    # No tenant filter on purpose: row-level security returns only this tenant's rows.
    result = await session.execute(select(Document).order_by(Document.created_at.desc()))
    return result.scalars().all()


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: uuid.UUID, session: AsyncSession = Depends(get_tenant_db)):
    await session.execute(delete(Chunk).where(Chunk.document_id == document_id))
    deleted = await session.scalar(
        delete(Document).where(Document.id == document_id).returning(Document.id)
    )
    if deleted is None:
        raise NotFoundError("Document not found")
    await session.execute(delete(SemanticCache))  # cached answers may cite the deleted document
    return Response(status_code=204)