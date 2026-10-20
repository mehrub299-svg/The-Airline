"""initial airline schema with RLS

Revision ID: 001
Revises:
Create Date: 2026-10-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = ["documents", "chunks", "chats", "messages", "semantic_cache"]


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )


def _tenant_id(primary_key: bool = False) -> sa.Column:
    return sa.Column(
        "tenant_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=primary_key,
        nullable=False,
    )


def upgrade() -> None:
    # ------------------------------------------------------------------ extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------ tenants
    op.create_table(
        "tenants",
        _uuid_pk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan_tier", sa.String(16), nullable=False, server_default="FREE"),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("token_bucket_coins", sa.Float(), nullable=False, server_default=sa.text("5.0")),
        sa.Column(
            "token_bucket_last_refill",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("monthly_tokens_used", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("monthly_token_limit", sa.BigInteger(), nullable=False, server_default=sa.text("50000")),
        sa.Column("chat_in_process_until", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint("plan_tier IN ('FREE', 'PRO')", name="ck_tenants_plan_tier"),
    )

    # ------------------------------------------------------------------ users
    op.create_table(
        "users",
        _uuid_pk(),
        _tenant_id(),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="MEMBER"),
        _created_at(),
        sa.CheckConstraint("role IN ('ADMIN', 'MEMBER')", name="ck_users_role"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------ refresh_tokens
    op.create_table(
        "refresh_tokens",
        _uuid_pk(),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _tenant_id(),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        _created_at(),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_tenant_id", "refresh_tokens", ["tenant_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    # ------------------------------------------------------------------ documents
    op.create_table(
        "documents",
        _uuid_pk(),
        _tenant_id(),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        _created_at(),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])

    # ------------------------------------------------------------------ chunks
    op.create_table(
        "chunks",
        _uuid_pk(),
        _tenant_id(),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
    )
    op.create_index("ix_chunks_tenant_id", "chunks", ["tenant_id"])
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])

    # ------------------------------------------------------------------ chats
    op.create_table(
        "chats",
        _uuid_pk(),
        _tenant_id(),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False, server_default="New chat"),
        _created_at(),
    )
    op.create_index("ix_chats_tenant_id", "chats", ["tenant_id"])
    op.create_index("ix_chats_user_id", "chats", ["user_id"])

    # ------------------------------------------------------------------ messages
    op.create_table(
        "messages",
        _uuid_pk(),
        _tenant_id(),
        sa.Column(
            "chat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        _created_at(),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
    )
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_messages_chat_id", "messages", ["chat_id"])

    # ------------------------------------------------------------------ semantic_cache
    op.create_table(
        "semantic_cache",
        _uuid_pk(),
        _tenant_id(),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("query_embedding", Vector(1536), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="THINKING_WAIT"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint("status IN ('THINKING_WAIT', 'READY')", name="ck_semantic_cache_status"),
    )
    op.create_index("ix_semantic_cache_tenant_id", "semantic_cache", ["tenant_id"])

    # ------------------------------------------------------------------ idempotency_keys
    op.create_table(
        "idempotency_keys",
        _tenant_id(primary_key=True),
        sa.Column("key", sa.String(255), primary_key=True, nullable=False),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="IN_PROCESS"),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=False),
        _created_at(),
        sa.CheckConstraint("status IN ('IN_PROCESS', 'COMPLETED')", name="ck_idempotency_status"),
    )

    # ------------------------------------------------------------------ feature_flags
    op.create_table(
        "feature_flags",
        _uuid_pk(),
        sa.Column("flag_key", sa.String(100), nullable=False),
        sa.Column("is_enabled_globally", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "tenant_overrides",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("ix_feature_flags_flag_key", "feature_flags", ["flag_key"], unique=True)

    # ------------------------------------------------------------------ seed feature flags
    op.execute(
        """
        INSERT INTO feature_flags (flag_key, is_enabled_globally, tenant_overrides)
        VALUES
            ('global_ai_master_switch', true, '{}'::jsonb),
            ('rag_v2', false, '{}'::jsonb)
        ON CONFLICT (flag_key) DO NOTHING
        """
    )

    # ------------------------------------------------------------------ tenant_user role (NOBYPASSRLS)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tenant_user') THEN
                CREATE ROLE tenant_user NOLOGIN NOBYPASSRLS;
            END IF;
        END
        $$
        """
    )
    # The connecting (owner) role must be allowed to SET ROLE tenant_user.
    op.execute("GRANT tenant_user TO CURRENT_USER")
    op.execute("GRANT USAGE ON SCHEMA public TO tenant_user")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tenant_user")

    # ------------------------------------------------------------------ RLS
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
                USING (tenant_id::text = current_setting('app.current_tenant', true))
                WITH CHECK (tenant_id::text = current_setting('app.current_tenant', true))
            """
        )


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")

    op.drop_table("feature_flags")
    op.drop_table("idempotency_keys")
    op.drop_table("semantic_cache")
    op.drop_table("messages")
    op.drop_table("chats")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("tenants")

    op.execute("REVOKE USAGE ON SCHEMA public FROM tenant_user")
    op.execute("DROP ROLE IF EXISTS tenant_user")