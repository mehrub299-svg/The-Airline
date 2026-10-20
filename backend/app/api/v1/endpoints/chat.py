from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services import rag

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat(body: ChatRequest, current_user: User = Depends(get_current_user)):
    prepared = await rag.prepare(current_user, body.message, body.chat_id, top_k=rag.TOP_K_V1)
    return StreamingResponse(
        rag.stream_answer(prepared),
        media_type="text/event-stream",
        headers=rag.SSE_HEADERS,
    )