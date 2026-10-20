from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.v1.router import router as v1_router
from app.api.v2.router import router as v2_router
from app.core.clients import close_http_client, init_http_client
from app.core.config import settings
from app.db.engine import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_http_client()
    yield
    await close_http_client()
    await engine.dispose()


app = FastAPI(title="The Airline", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # explicit whitelist, never "*"
    allow_credentials=False,  # auth is a bearer header, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

register_exception_handlers(app)

app.include_router(v1_router, prefix="/api/v1")
app.include_router(v2_router, prefix="/api/v2")