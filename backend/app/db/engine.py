from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=300,
    # Safe on both Neon direct and pooled (pgbouncer) endpoints.
    connect_args={"statement_cache_size": 0},
)