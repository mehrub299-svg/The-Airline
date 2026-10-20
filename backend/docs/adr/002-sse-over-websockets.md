# ADR 002: Server-Sent Events for chat streaming

Status: Accepted (2026-10-20)

## Context
Chat answers stream token by token from OpenRouter. Data flows one way (server to client) once a question is sent.
The service runs on a free tier behind ordinary HTTP infrastructure.

## Decision
Stream with `StreamingResponse(media_type="text/event-stream")`, emitting `data: {"token": "..."}` events, plus
`chat_id`, `done` and `error` events. The client reads the stream with `fetch` so it can send the bearer header.

- Everything that can fail (feature flags, rate limits, cache lookup, quota, the OpenRouter connect) runs before the
  response starts, so clients get real HTTP status codes. Failures after that arrive as an SSE `error` event.
- Token accounting runs in the generator's `finally:` block, shielded from cancellation, on an independent database
  session. If the user clicks Stop, the tenant is still charged `prompt_tokens_est + streamed_chars // 4`
  (or the provider's reported usage when the stream finished) and the per-tenant chat lock is cleared.

## Consequences
- No connection upgrade, no extra protocol, works through standard proxies. Responses send `X-Accel-Buffering: no`
  so Nginx does not buffer them.
- A client cannot send messages mid-stream; stopping is done by closing the request.
- If a client disconnects before the first byte is read, the generator never starts. The 120 second expiry of
  `chat_in_process_until` is the backstop.
- Rejected: WebSockets (bidirectional capability not needed, more moving parts, harder to authenticate and proxy).