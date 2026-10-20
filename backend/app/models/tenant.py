import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Float, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("plan_tier IN ('FREE', 'PRO')", name="ck_tenants_plan_tier"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_tier: Mapped[str] = mapped_column(
        String(16), nullable=False, default="FREE", server_default="FREE"
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Door 1 token bucket (capacity 5.0, refill 0.1 coins/sec)
    token_bucket_coins: Mapped[float] = mapped_column(
        Float, nullable=False, default=5.0, server_default=text("5.0")
    )
    token_bucket_last_refill: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Door 2 monthly quota
    monthly_tokens_used: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    monthly_token_limit: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=50000, server_default=text("50000")
    )

    # Blocks parallel streams from the same tenant
    chat_in_process_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )