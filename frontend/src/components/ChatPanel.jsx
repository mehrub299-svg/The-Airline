import Markdown from "./Markdown.jsx";
import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

let counter = 0;
const uid = () => `m${Date.now()}-${counter++}`;

export default function ChatPanel({
  initialChatId,
  documentIds,
  lockedMessage,
  paused,
  scopeText,
  useV2,
  onChatCreated,
  onChatsChanged,
  onUsage,
  onChatError,
}) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(Boolean(initialChatId));
  const [loadError, setLoadError] = useState("");
  const [input, setInput] = useState("");
  const [chatId, setChatId] = useState(initialChatId);
  const [busy, setBusy] = useState(false);
  const controllerRef = useRef(null);
  const endRef = useRef(null);

  // Opening an existing chat: load its saved messages.
  useEffect(() => {
    if (!initialChatId) return;
    let cancelled = false;
    api
      .chatMessages(initialChatId)
      .then((rows) => {
        if (!cancelled) {
          setMessages(rows.map((m) => ({ id: m.id, role: m.role, text: m.content, status: "done" })));
        }
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [initialChatId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const locked = Boolean(lockedMessage);

  const patch = (id, update) =>
    setMessages((all) => all.map((m) => (m.id === id ? update(m) : m)));

  async function send() {
    const question = input.trim();
    if (!question || busy || locked || loading) return;

    const assistantId = uid();
    setInput("");
    setBusy(true);
    setMessages((all) => [
      ...all,
      { id: uid(), role: "user", text: question },
      { id: assistantId, role: "assistant", text: "", status: "streaming" },
    ]);

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      await api.streamChat({
        message: question,
        chatId,
        documentIds,
        useV2,
        signal: controller.signal,
        onEvent: (event) => {
          if (event.chat_id) {
            setChatId(event.chat_id);
            if (!chatId) onChatCreated(event.chat_id);
          }
          if (event.token) patch(assistantId, (m) => ({ ...m, text: m.text + event.token }));
          if (event.error) patch(assistantId, (m) => ({ ...m, status: "error", error: event.error }));
          if (event.done) patch(assistantId, (m) => ({ ...m, status: "done" }));
        },
      });
      patch(assistantId, (m) => (m.status === "streaming" ? { ...m, status: "done" } : m));
    } catch (err) {
      if (err.name === "AbortError") {
        patch(assistantId, (m) => ({ ...m, status: "stopped" }));
      } else {
        patch(assistantId, (m) => ({
          ...m,
          status: "error",
          error: err.message,
          retryAfter: err.retryAfter,
        }));
        onChatError();
      }
    } finally {
      controllerRef.current = null;
      setBusy(false);
      onChatsChanged();
      onUsage();
      setTimeout(onUsage, 1500); // the server records usage just after the stream closes
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      {paused && (
        <p role="status" className="mx-5 mt-4 rounded-lg bg-signal/30 px-4 py-3 text-sm">
          The assistant is down for maintenance. Your documents are still available.
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
        {loading ? (
          <p className="text-sm text-muted">Loading conversation…</p>
        ) : loadError ? (
          <p role="alert" className="text-sm text-alert">
            {loadError}
          </p>
        ) : messages.length === 0 ? (
          <div className="grid h-full place-items-center text-center">
            <p className="max-w-sm text-muted">
              Ask a question and the answer is drawn only from your uploaded documents.
            </p>
          </div>
        ) : (
          <ol className="space-y-6">
            {messages.map((m) => (
              <li key={m.id}>
                {m.role === "user" ? (
                  <div className="ml-auto w-fit max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm bg-brand px-4 py-3 text-onbrand">
                    {m.text}
                  </div>
                ) : (
                  <div className="max-w-[46rem] border-l-4 border-signal pl-4">
                    {m.text ? (
                      <div className={`break-words ${m.status === "streaming" ? "caret" : ""}`}>
                        <Markdown text={m.text} />
                      </div>
                    ) : (
                      m.status === "streaming" && (
                        <p className="caret text-muted">Searching your documents</p>
                      )
                    )}
                    {m.status === "stopped" && <p className="mt-1 text-xs text-muted">Stopped.</p>}
                    {m.status === "error" && (
                      <p role="alert" className="mt-1 text-sm text-alert">
                        {m.error}
                        {m.retryAfter ? ` Try again in ${m.retryAfter} seconds.` : ""}
                      </p>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className="border-t border-line p-4"
      >
        <div className="flex items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={2}
            maxLength={4000}
            disabled={locked}
            placeholder={lockedMessage || "Ask a question about your documents"}
            aria-label="Your question"
            className="min-h-[3.25rem] flex-1 resize-none rounded-xl border border-line bg-surface px-4 py-3 text-ink placeholder:text-muted/70 disabled:opacity-60"
          />
          {busy ? (
            <button
              type="button"
              onClick={() => controllerRef.current?.abort()}
              className="rounded-xl border border-ink px-5 py-3 font-semibold"
            >
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={locked || loading || !input.trim()}
              className="rounded-xl bg-brand px-5 py-3 font-semibold text-onbrand hover:bg-brand-hover disabled:opacity-50"
            >
              Send
            </button>
          )}
        </div>
        <p className="mt-2 text-xs text-muted">
          {scopeText} Each question is answered on its own. Enter sends, Shift+Enter adds a line.
        </p>
      </form>
    </div>
  );
}