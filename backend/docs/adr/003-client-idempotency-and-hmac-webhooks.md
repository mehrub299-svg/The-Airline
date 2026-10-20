# ADR 003: Client idempotency keys and HMAC-verified webhooks

Status: Accepted (2026-10-20)

## Context
Uploads and checkouts are expensive or money-related and must not run twice when a client retries. Payment
webhooks are delivered at least once and can be forged if the sender is not verified.

## Decision
Idempotency:
- Clients send `Idempotency-Key: <uuid>` on `POST /api/v1/documents` and `POST /api/v1/billing/checkout`.
- State lives in `idempotency_keys` with primary key `(tenant_id, key)`. A claim is
  `INSERT ... ON CONFLICT DO NOTHING` with `locked_until = now() + 60 seconds`, status `IN_PROCESS`.
- Duplicate while the lock is alive: 409. Duplicate after a crash (lock expired): the new request takes over
  atomically. Duplicate after success: the saved response code and body are replayed without re-running.
- Failed requests release their claim so the client can retry at once.

Webhooks:
- `POST /api/v1/billing/webhooks/stripe` reads the raw request bytes and verifies `Stripe-Signature`
  (`t=<timestamp>,v1=<hex>`) with HMAC-SHA256 over `<timestamp>.<raw body>`, a constant-time comparison
  (`hmac.compare_digest`) and a 300 second replay window. Python's `hmac` and `hashlib` are enough; no SDK is
  needed to verify.
- The Stripe event id is recorded in the same table, so a re-delivered event is a no-op.
- `checkout.session.completed` upgrades the tenant to PRO with a 1,000,000 token monthly limit.

Billing modes: `STRIPE_SECRET_KEY=sandbox_no_bank` simulates a paid checkout through the same event handler, so the
whole flow runs with no bank account. A real `sk_test_` or `sk_live_` key switches to Stripe Checkout with no
code change.

## Consequences
- Sandbox mode upgrades a tenant without payment. It must never be left on in a paying client's deployment.
- Only `checkout.session.completed` is handled. Cancellations and failed renewals do not downgrade a tenant yet.