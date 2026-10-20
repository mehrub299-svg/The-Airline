from fastapi import APIRouter

from app.api.v1.endpoints import auth, billing, chat, documents, flags, health

router = APIRouter()
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(documents.router)
router.include_router(chat.router)
router.include_router(billing.router)
router.include_router(flags.router)