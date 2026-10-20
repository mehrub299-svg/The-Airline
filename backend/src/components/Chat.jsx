import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

let counter = 0;
const uid = () => `m${Date.now()}-${counter++}`;

export default function Chat({ docCount, paused, showV2, onUsage, onChatError }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [chatId, setChatId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [useV2, setUseV2] = useState(false);
  const controllerRef = useRef(null);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const noDocs = docCount === 0;
  const locked = paused || noDocs;
  const placeholder = paused
    ? "Chat is paused for maintenance."
    : noDocs
    ? "Upload a document to start asking questions."
    : "Ask a question about your documents";

  const patch = (id, update) =>
    setMessages((all) => all.map((m) => (m.id === id ? update(m) : m)));

  async function send() {
    const question = input.trim();
    if (!question || busy || locked) return;

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
        useV2: showV2 && useV2,
        signal: controller.signal,
        onEvent: (event) => {
          if (event.chat_id) setChatId(event.chat_id);
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
      onUsage();
      setTimeout(onUsage, 1500); // the server records usage just after the stream closes
    }
  }

  function newChat() {
    setMessages([]);
    setChatId(null);
  }

  return (
    <section className="flex h-full min-h-0 flex-col rounded-2xl bg-white ring-1 ring-mist">
      <div className="flex items-center justify-between gap-4 px-5 pt-4">
        <h2 className="font-display text-lg font-bold">Chat</h2>
        <div className="flex items-center gap-4">
          {showV2 && (
            <label className="flex items-center gap-2 text-sm text-steel">
              <input type="checkbox" checked={useV2} onChange={(e) => setUseV2(e.target.checked)} />
              Use RAG v2
            </label>
          )}
          <button
            onClick={newChat}
            disabled={busy || messages.length === 0}
            className="text-sm font-semibold text-steel underline disabled:opacity-40"
          >
            Start new chat
          </button>
        </div>
      </div>

      {paused && (
        <p role="status" className="mx-5 mt-3 rounded-lg bg-signal/30 px-4 py-3 text-sm">
          The assistant is down for maintenance. Your documents are still available.
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
        {messages.length === 0 ? (
          <div className="grid h-full place-items-center text-center">
            <p className="max-w-sm text-steel">
              Ask a question and the answer is drawn only from your uploaded documents.
            </p>
          </div>
        ) : (
          <ol className="space-y-6">
            {messages.map((m) => (
              <li key={m.id}>
                {m.role === "user" ? (
                  <div className="ml-auto w-fit max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm bg-navy px-4 py-3 text-white">
                    {m.text}
                  </div>
                ) : (
                  <div className="max-w-[46rem] border-l-4 border-signal pl-4">
                    {m.text ? (
                      <p
                        className={`whitespace-pre-wrap break-words leading-relaxed ${
                          m.status === "streaming" ? "caret" : ""
                        }`}
                      >
                        {m.text}
                      </p>
                    ) : (
                      m.status === "streaming" && <p className="caret text-steel">Searching your documents</p>
                    )}
                    {m.status === "stopped" && <p className="mt-1 text-xs text-steel">Stopped.</p>}
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
        className="border-t border-mist/70 p-4"
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
            placeholder={placeholder}
            aria-label="Your question"
            className="min-h-[3.25rem] flex-1 resize-none rounded-xl border border-mist px-4 py-3 disabled:bg-altitude"
          />
          {busy ? (
            <button
              type="button"
              onClick={() => controllerRef.current?.abort()}
              className="rounded-xl border border-navy px-5 py-3 font-semibold text-navy"
            >
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={locked || !input.trim()}
              className="rounded-xl bg-navy px-5 py-3 font-semibold text-white hover:bg-navy-soft disabled:opacity-50"
            >
              Send
            </button>
          )}
        </div>
        <p className="mt-2 text-xs text-steel">
          Each question is answered on its own, from your documents. Enter sends, Shift+Enter adds a line.
        </p>
      </form>
    </section>
  );
}