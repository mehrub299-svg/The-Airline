from typing import Literal

from pydantic import BaseModel


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    mode: Literal["sandbox", "live"]


class BillingStatusResponse(BaseModel):
    plan_tier: str
    monthly_tokens_used: int
    monthly_token_limit: int
    billing_mode: Literal["sandbox", "live"]