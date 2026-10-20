import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import anyio
import httpx
from sqlalchemy import select, update

from app.api.ratelimit import acquire_chat_slot, check_monthly_quota, release_chat_slot
from app.db.session import AsyncSessionLocal, tenant_session
from app.models.chat import Chat, Message
from app.models.tenant import Tenant
from app.models.user import User
from app.services import feature_flags, llm, semantic_cache
from app.services.embedding import embed_query
from app.services.exceptions import NotFoundError, RateLimitError
from app.services.llm import UpstreamStream
from app.services.retrieval import retrieve_chunks

logger = logging.getLogger("airline.rag")

TOP_K_V1 = 5
TOP_K_V2 = 8

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

NO_DOCUMENTS_TEXT = (
    "I couldn't find any uploaded documents to answer from. Please upload a document first."
)
_STATIC_SLICE = 24  # characters per SSE event when replaying cached/canned text


@dataclass
class PreparedAnswer:
    tenant_id: uuid.UUID
    chat_id: uuid.UUID
    static_text: str | None  # cache hit or canned answer: no OpenRouter call
    upstream: UpstreamStream | None  # live OpenRouter stream
    cache_id: uuid.UUID | None  # THINKING_WAIT row to resolve when the stream ends


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _save_user_message(user: User, chat_id: uuid.UUID | None, question: str) -> uuid.UUID:
    async with tenant_session(user.tenant_id) as session:
        if chat_id is None:
            chat = Chat(tenant_id=user.tenant_id, user_id=user.id, title=" ".join(question.split())[:60])
            session.add(chat)
            await session.flush()
            chat_id = chat.id
        session.add(
            Message(tenant_id=user.tenant_id, chat_id=chat_id, role="user", content=question, tokens_used=0)
        )
    return chat_id


async def _undo_prepare(
    tenant_id: uuid.UUID, cache_id: uuid.UUID | None, upstream: UpstreamStream | None
) -> None:
    with anyio.CancelScope(shield=True):
        if upstream is not None:
            try:
                await upstream.response.aclose()
            except Exception:
                logger.exception("Failed to close upstream stream")
        if cache_id is not None:
            try:
                async with tenant_session(tenant_id) as session:
                    await semantic_cache.discard(session, cache_id)
            except Exception:
                logger.exception("Failed to discard cache claim")
        try:
            await release_chat_slot(tenant_id)
        except Exception:
            logger.exception("Failed to release chat slot")


async def prepare(user: User, question: str, chat_id: uuid.UUID | None, top_k: int) -> PreparedAnswer:
    """Everything that can fail runs here, BEFORE the streaming response starts, so errors are real
    HTTP statuses (503, 429, 404). On any failure the chat lock and cache claim are undone."""
    tenant_id = user.tenant_id

    await feature_flags.require_ai_enabled()  # master switch: 503 without touching the DB or OpenRouter

    if chat_id is not None:
        async with tenant_session(tenant_id) as session:
            exists = await session.scalar(select(Chat.id).where(Chat.id == chat_id))
        if exists is None:
            raise NotFoundError("Chat not found")

    await acquire_chat_slot(tenant_id)  # Door 1: token bucket + one stream at a time

    cache_id: uuid.UUID | None = None
    upstream: UpstreamStream | None = None
    try:
        embedding = await embed_query(question)

        async with tenant_session(tenant_id) as session:  # semantic cache (middle)
            found = await semantic_cache.lookup(session, embedding)
            chunks: list[str] = []
            if found.kind == "miss":
                chunks = await retrieve_chunks(session, embedding, top_k)

        static_text: str | None = None
        if found.kind == "in_flight":
            raise RateLimitError("Duplicate Query In Flight", retry_after=5)
        if found.kind == "hit":
            static_text = found.response_text
        elif not chunks:
            static_text = NO_DOCUMENTS_TEXT
        else:
            await check_monthly_quota(tenant_id)  # Door 2: after a cache miss, before OpenRouter
            async with tenant_session(tenant_id) as session:
                cache_id = await semantic_cache.claim(session, tenant_id, question, embedding)
            upstream = await llm.open_stream(question, chunks)

        saved_chat_id = await _save_user_message(user, chat_id, question)
        return PreparedAnswer(
            tenant_id=tenant_id,
            chat_id=saved_chat_id,
            static_text=static_text,
            upstream=upstream,
            cache_id=cache_id,
        )
    except BaseException:
        await _undo_prepare(tenant_id, cache_id, upstream)
        raise


async def _finalize(
    p: PreparedAnswer,
    answer: str,
    streamed_chars: int,
    reported_tokens: int | None,
    completed: bool,
) -> None:
    if p.upstream is not None:
        billed = (
            reported_tokens
            if reported_tokens is not None
            else p.upstream.prompt_tokens_est + streamed_chars // 4
        )
    else:
        billed = 0  # cache hits and canned answers cost nothing

    # 1) Billing + chat lock release. Independent owner session; must never be skipped.
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Tenant)
                .where(Tenant.id == p.tenant_id)
                .values(
                    monthly_tokens_used=Tenant.monthly_tokens_used + billed,
                    chat_in_process_until=None,
                )
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to record token usage / release chat lock")

    # 2) Close the upstream connection.
    if p.upstream is not None:
        try:
            await p.upstream.response.aclose()
        except Exception:
            logger.exception("Failed to close upstream stream")

    # 3) Resolve the cache claim and save the assistant message (partial answers are saved, not cached).
    try:
        async with tenant_session(p.tenant_id) as session:
            if p.cache_id is not None:
                if completed and answer:
                    await semantic_cache.mark_ready(session, p.cache_id, answer)
                else:
                    await semantic_cache.discard(session, p.cache_id)
            if answer:
                session.add(
                    Message(
                        tenant_id=p.tenant_id,
                        chat_id=p.chat_id,
                        role="assistant",
                        content=answer,
                        tokens_used=billed,
                    )
                )
    except Exception:
        logger.exception("Failed to save assistant message / resolve cache entry")


async def stream_answer(p: PreparedAnswer) -> AsyncIterator[str]:
    answer_parts: list[str] = []
    streamed_chars = 0
    reported_tokens: int | None = None
    completed = False

    try:
        yield _sse({"chat_id": str(p.chat_id)})

        if p.static_text is not None:
            for start in range(0, len(p.static_text), _STATIC_SLICE):
                piece = p.static_text[start : start + _STATIC_SLICE]
                answer_parts.append(piece)
                yield _sse({"token": piece})
            completed = True
        else:
            failed = False
            try:
                async for kind, value in llm.iter_events(p.upstream.response):
                    if kind == "token":
                        streamed_chars += len(value)
                        answer_parts.append(value)
                        yield _sse({"token": value})
                    elif kind == "usage":
                        reported_tokens = value
                    else:
                        failed = True
                        break
            except httpx.HTTPError as exc:
                logger.error("Upstream stream failed: %s", exc)
                failed = True

            if failed:
                yield _sse({"error": "The AI provider failed while answering"})
            else:
                completed = True

        if completed:
            yield _sse({"done": True})
    finally:
        # Runs on normal end, errors, and when the user clicks Stop (GeneratorExit / CancelledError).
        # The shield keeps the cleanup alive even though the surrounding request was cancelled.
        with anyio.CancelScope(shield=True):
            await _finalize(p, "".join(answer_parts), streamed_chars, reported_tokens, completed)