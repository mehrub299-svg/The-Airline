from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services import feature_flags, rag
from app.services.exceptions import PermissionDeniedError

router = APIRouter(prefix="/chat", tags=["chat-v2"])


@router.post("")
async def chat_v2(body: ChatRequest, current_user: User = Depends(get_current_user)):
    await feature_flags.require_ai_enabled()  # maintenance (503) takes priority over the flag check
    if not await feature_flags.is_enabled(feature_flags.RAG_V2, current_user.tenant_id):
        raise PermissionDeniedError("RAG v2 is not enabled for your workspace")

    prepared = await rag.prepare(current_user, body.message, body.chat_id, top_k=rag.TOP_K_V2)
    return StreamingResponse(
        rag.stream_answer(prepared),
        media_type="text/event-stream",
        headers=rag.SSE_HEADERS,
    )