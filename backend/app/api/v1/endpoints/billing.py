import uuid

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.billing import BillingStatusResponse, CheckoutResponse
from app.services import billing, idempotency

router = APIRouter(prefix="/billing", tags=["billing"])

_ENDPOINT = "POST /billing/checkout"


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
):
    tenant_id = current_user.tenant_id
    key = str(idempotency_key)

    outcome = await idempotency.begin(tenant_id, key, _ENDPOINT)
    if outcome.replay:
        return JSONResponse(status_code=outcome.response_code, content=outcome.response_body)

    try:
        result = await billing.create_checkout(current_user, key)
        await idempotency.complete(tenant_id, key, 200, result.model_dump(mode="json"))
    except Exception:
        await idempotency.release(tenant_id, key)
        raise
    return result


@router.get("/status", response_model=BillingStatusResponse)
async def billing_status(current_user: User = Depends(get_current_user)):
    return await billing.get_status(current_user.tenant_id)


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    raw_body = await request.body()  # exact bytes: the signature covers them, so never re-serialize
    return await billing.handle_webhook(raw_body, stripe_signature)