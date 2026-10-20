from fastapi import APIRouter

from app.api.v2.endpoints import chat

router = APIRouter()
router.include_router(chat.router)