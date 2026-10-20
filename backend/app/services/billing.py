import hashlib
import hmac
import json
import logging
import time
import uuid

from sqlalchemy import update

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.billing import BillingStatusResponse, CheckoutResponse
from app.services import idempotency
from app.services.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)

logger = logging.getLogger("airline.billing")

PRO_MONTHLY_TOKEN_LIMIT = 1_000_000
SIGNATURE_TOLERANCE_SECONDS = 300


def _billing_mode() -> str:
    return "sandbox" if settings.stripe_sandbox_mode else "live"


# --------------------------------------------------------------------------- webhook verification
def _parse_signature_header(header: str) -> tuple[str, int, list[str]]:
    """Stripe-Signature looks like: t=<timestamp>,v1=<hex>[,v1=<hex>...]"""
    timestamp_raw = ""
    signatures: list[str] = []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp_raw = value
        elif key == "v1":
            signatures.append(value)
    try:
        timestamp = int(timestamp_raw)
    except ValueError:
        raise BadRequestError("Invalid webhook signature")
    if not signatures:
        raise BadRequestError("Invalid webhook signature")
    return timestamp_raw, timestamp, signatures


def verify_stripe_signature(
    raw_body: bytes, header: str | None, secret: str, now: float | None = None
) -> None:
    """HMAC-SHA256 over '<timestamp>.<raw body bytes>', constant-time compare, 300 s replay window."""
    if not header:
        raise BadRequestError("Missing Stripe-Signature header")

    timestamp_raw, timestamp, signatures = _parse_signature_header(header)
    signed_payload = timestamp_raw.encode("utf-8") + b"." + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()

    if not any(hmac.compare_digest(expected.encode(), sig.encode()) for sig in signatures):
        raise BadRequestError("Invalid webhook signature")

    current = time.time() if now is None else now
    if abs(current - timestamp) > SIGNATURE_TOLERANCE_SECONDS:
        raise BadRequestError("Webhook timestamp is outside the allowed window")


# --------------------------------------------------------------------------- event processing
def _tenant_id_from(session_object: dict) -> uuid.UUID | None:
    candidate = (session_object.get("metadata") or {}).get("tenant_id") or session_object.get(
        "client_reference_id"
    )
    try:
        return uuid.UUID(str(candidate))
    except (ValueError, TypeError):
        return None


async def _upgrade_tenant(tenant_id: uuid.UUID, customer_id: str | None) -> None:
    values: dict = {"plan_tier": "PRO", "monthly_token_limit": PRO_MONTHLY_TOKEN_LIMIT}
    if customer_id:
        values["stripe_customer_id"] = customer_id
    async with AsyncSessionLocal() as session:
        await session.execute(update(Tenant).where(Tenant.id == tenant_id).values(**values))
        await session.commit()


async def process_event(event: dict) -> dict:
    """Shared by the real webhook and by sandbox checkout. Duplicate event ids are harmless no-ops."""
    event_id = event.get("id")
    if event.get("type") != "checkout.session.completed" or not event_id:
        return {"received": True, "ignored": True}

    session_object = (event.get("data") or {}).get("object") or {}
    if session_object.get("payment_status") not in ("paid", "no_payment_required"):
        return {"received": True, "ignored": True}

    tenant_id = _tenant_id_from(session_object)
    if tenant_id is None:
        logger.warning("checkout.session.completed %s has no valid tenant id; ignored", event_id)
        return {"received": True, "ignored": True}

    outcome = await idempotency.begin(tenant_id, event_id, "stripe_webhook")
    if outcome.replay:
        return {"received": True, "duplicate": True}

    try:
        await _upgrade_tenant(tenant_id, session_object.get("customer"))
        result = {"received": True}
        await idempotency.complete(tenant_id, event_id, 200, result)
    except Exception:
        await idempotency.release(tenant_id, event_id)
        raise
    return result


async def handle_webhook(raw_body: bytes, signature_header: str | None) -> dict:
    verify_stripe_signature(raw_body, signature_header, settings.STRIPE_WEBHOOK_SECRET)
    try:
        event = json.loads(raw_body)
    except ValueError:
        raise BadRequestError("Invalid webhook payload")
    if not isinstance(event, dict):
        raise BadRequestError("Invalid webhook payload")
    return await process_event(event)


# --------------------------------------------------------------------------- checkout + status
async def create_checkout(user: User, idempotency_key: str) -> CheckoutResponse:
    tenant_id = user.tenant_id

    async with AsyncSessionLocal() as session:
        tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Workspace not found")
    if tenant.plan_tier == "PRO":
        raise ConflictError("Workspace is already on the PRO plan")

    if settings.stripe_sandbox_mode:
        # No bank, no Stripe account: simulate a paid checkout through the same code path as the webhook.
        session_id = f"cs_sandbox_{uuid.uuid4().hex}"
        await process_event(
            {
                "id": f"evt_sandbox_{uuid.uuid4().hex}",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": session_id,
                        "payment_status": "paid",
                        "customer": None,
                        "client_reference_id": str(tenant_id),
                        "metadata": {"tenant_id": str(tenant_id)},
                    }
                },
            }
        )
        return CheckoutResponse(
            checkout_url=f"{settings.FRONTEND_URL}?checkout=success",
            session_id=session_id,
            mode="sandbox",
        )

    if not settings.STRIPE_PRO_PRICE_ID:
        raise ServiceUnavailableError("Billing is not configured")

    import stripe  # imported lazily so sandbox mode works without the package

    params: dict = {
        "mode": "subscription",
        "line_items": [{"price": settings.STRIPE_PRO_PRICE_ID, "quantity": 1}],
        "success_url": f"{settings.FRONTEND_URL}?checkout=success",
        "cancel_url": f"{settings.FRONTEND_URL}?checkout=cancelled",
        "client_reference_id": str(tenant_id),
        "metadata": {"tenant_id": str(tenant_id)},
    }
    if tenant.stripe_customer_id:
        params["customer"] = tenant.stripe_customer_id
    else:
        params["customer_email"] = user.email

    try:
        session = await stripe.checkout.Session.create_async(
            api_key=settings.STRIPE_SECRET_KEY,
            idempotency_key=f"{tenant_id}:{idempotency_key}",
            **params,
        )
    except stripe.StripeError as exc:
        logger.error("Stripe checkout creation failed: %s", exc)
        raise ServiceUnavailableError("Payment provider unavailable")

    if not session.url:
        raise ServiceUnavailableError("Payment provider returned no checkout URL")
    return CheckoutResponse(checkout_url=session.url, session_id=session.id, mode="live")


async def get_status(tenant_id: uuid.UUID) -> BillingStatusResponse:
    async with AsyncSessionLocal() as session:
        tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Workspace not found")
    return BillingStatusResponse(
        plan_tier=tenant.plan_tier,
        monthly_tokens_used=tenant.monthly_tokens_used,
        monthly_token_limit=tenant.monthly_token_limit,
        billing_mode=_billing_mode(),
    )