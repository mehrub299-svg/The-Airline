import uuid

from fastapi import APIRouter, Depends ,Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select ,delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_tenant_db
from app.models.chat import Chat, Message
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatSummary, MessageOut
from app.services import rag
from app.services.exceptions import NotFoundError

router = APIRouter(tags=["chat"])

MAX_CHATS = 100


@router.post("/chat")
async def chat(body: ChatRequest, current_user: User = Depends(get_current_user)):
    document_ids = list(dict.fromkeys(body.document_ids)) if body.document_ids else None
    prepared = await rag.prepare(
        current_user, body.message, body.chat_id, top_k=rag.TOP_K_V1, document_ids=document_ids
    )
    return StreamingResponse(
        rag.stream_answer(prepared),
        media_type="text/event-stream",
        headers=rag.SSE_HEADERS,
    )


@router.get("/chats", response_model=list[ChatSummary])
async def list_chats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_db),
):
    result = await session.scalars(
        select(Chat)
        .where(Chat.user_id == current_user.id)
        .order_by(Chat.created_at.desc())
        .limit(MAX_CHATS)
    )
    return result.all()


@router.get("/chats/{chat_id}/messages", response_model=list[MessageOut])
async def chat_messages(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_db),
):
    owned = await session.scalar(
        select(Chat.id).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    )
    if owned is None:
        raise NotFoundError("Chat not found")

    result = await session.scalars(
        select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at, Message.id)
    )
    return result.all()

@router.delete("/chats/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_db),
):
    owned = await session.scalar(
        select(Chat.id).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    )
    if owned is None:
        raise NotFoundError("Chat not found")

    await session.execute(delete(Message).where(Message.chat_id == chat_id))
    await session.execute(delete(Chat).where(Chat.id == chat_id))
    return Response(status_code=204)