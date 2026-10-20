# ADR 001: PostgreSQL row-level security for multi-tenancy

Status: Accepted (2026-10-20)

## Context
The Airline is a multi-tenant RAG SaaS. A tenant must never read or write another tenant's documents,
chunks, chats, messages or cached answers. A forgotten `WHERE tenant_id = ...` in application code
would be a data leak, and vector search makes such queries easy to get subtly wrong.

## Decision
Isolation is enforced by the database, not by application code.

- Tables `documents`, `chunks`, `chats`, `messages` and `semantic_cache` have `ENABLE` and `FORCE ROW LEVEL SECURITY`
  with one policy each: `tenant_id::text = current_setting('app.current_tenant', true)` for both USING and WITH CHECK.
- Neon's default owner role has BYPASSRLS, so the migration creates a `tenant_user` role (NOLOGIN, NOBYPASSRLS).
- Every tenant-scoped transaction runs `SET LOCAL ROLE tenant_user` and then
  `SELECT set_config('app.current_tenant', :tid, true)`. The second form equals `SET LOCAL` but accepts a
  bind parameter, which a plain `SET` does not. Both settings last only until the transaction ends, so pooled
  connections come back clean.
- All of this lives in one helper, `tenant_session()` in `app/db/session.py`. `get_tenant_db` wraps it.

## Consequences
- A query that forgets a tenant filter returns zero foreign rows instead of leaking them.
- Code inside `tenant_session` must `flush()`, never `commit()`: a commit would end the transaction and the next
  statement would run as the owner role, which bypasses RLS. The transaction commits when the block exits.
- `tenants`, `users`, `refresh_tokens`, `idempotency_keys` and `feature_flags` are not under RLS. They are reached
  only through services that pass an explicit tenant id.
- Any new table needs its own `GRANT` to `tenant_user`, and an RLS policy if it holds tenant data.
- Rejected: schema-per-tenant (migration cost per tenant, poor fit for a free tier) and application-level filtering only.