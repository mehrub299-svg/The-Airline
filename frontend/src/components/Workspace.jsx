import { useEffect, useState } from "react";
import { api } from "../api.js";
import Chat from "./Chat.jsx";
import Documents from "./Documents.jsx";

const fmt = (n) => new Intl.NumberFormat().format(n);

export default function Workspace({
  user,
  flags,
  billing,
  initialNotice,
  refreshBilling,
  refreshFlags,
  onSignOut,
}) {
  const [docs, setDocs] = useState(null);
  const [panel, setPanel] = useState("chat");
  const [notice, setNotice] = useState(initialNotice ? { tone: "info", text: initialNotice } : null);
  const [upgrading, setUpgrading] = useState(false);

  useEffect(() => {
    api
      .documents()
      .then(setDocs)
      .catch((err) => {
        setDocs([]);
        setNotice({ tone: "error", text: `Couldn't load your documents. ${err.message}` });
      });
  }, []);

  const isPro = billing?.plan_tier === "PRO";
  const used = billing?.monthly_tokens_used ?? 0;
  const limit = billing?.monthly_token_limit ?? 0;
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;

  async function upgrade() {
    setUpgrading(true);
    setNotice(null);
    try {
      const result = await api.checkout();
      if (result.mode === "live") {
        window.location.assign(result.checkout_url);
        return;
      }
      await refreshBilling();
      setNotice({
        tone: "info",
        text: "Your workspace is now on Pro. This is sandbox billing: no payment was taken.",
      });
    } catch (err) {
      setNotice({ tone: "error", text: err.message });
    } finally {
      setUpgrading(false);
    }
  }

  return (
    <div className="flex h-dvh flex-col">
      <header className="px-4 pt-4 md:px-6 md:pt-5">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <h1 className="wordmark text-[1.7rem] text-navy md:text-[2.1rem]">THE AIRLINE</h1>

          <div className="ml-auto flex flex-wrap items-center gap-3 md:gap-5">
            <span className="hidden text-sm text-steel lg:block">{user.email}</span>

            {billing && (
              <div className="min-w-[11rem]">
                <div className="flex justify-between text-xs text-steel">
                  <span>Token usage</span>
                  <span>
                    {fmt(used)} of {fmt(limit)}
                  </span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-mist/70">
                  <div
                    className={`h-full rounded-full ${pct >= 90 ? "bg-alert" : "bg-navy"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            )}

            {billing && (
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  isPro ? "bg-signal text-navy" : "bg-mist/70 text-navy"
                }`}
              >
                {isPro ? "Pro" : "Free"}
              </span>
            )}

            {billing && !isPro && (
              <button
                onClick={upgrade}
                disabled={upgrading}
                className="rounded-lg bg-navy px-4 py-2 text-sm font-semibold text-white hover:bg-navy-soft disabled:opacity-60"
              >
                {upgrading ? "Upgrading…" : "Upgrade to Pro"}
              </button>
            )}

            <button
              onClick={onSignOut}
              className="rounded-lg border border-mist bg-white px-4 py-2 text-sm font-semibold text-navy"
            >
              Sign out
            </button>
          </div>
        </div>
        <div className="runway mt-4" aria-hidden="true" />
      </header>

      {notice && (
        <div
          role={notice.tone === "error" ? "alert" : "status"}
          className={`mx-4 mt-3 flex items-start justify-between gap-4 rounded-lg px-4 py-3 text-sm md:mx-6 ${
            notice.tone === "error" ? "bg-alert/10 text-alert" : "bg-white text-navy ring-1 ring-mist"
          }`}
        >
          <span>{notice.text}</span>
          <button onClick={() => setNotice(null)} className="shrink-0 font-semibold underline">
            Dismiss
          </button>
        </div>
      )}

      <div className="flex gap-2 px-4 pt-3 md:hidden">
        {[
          ["chat", "Chat"],
          ["docs", "Documents"],
        ].map(([id, label]) => (
          <button
            key={id}
            aria-pressed={panel === id}
            onClick={() => setPanel(id)}
            className={`flex-1 rounded-full py-2.5 text-sm font-semibold ${
              panel === id ? "bg-navy text-white" : "bg-white text-steel ring-1 ring-mist"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <main className="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)] gap-4 p-4 md:grid-cols-[22rem_1fr] md:p-6">
        <div className={`${panel === "docs" ? "block" : "hidden"} min-h-0 md:block`}>
          <Documents docs={docs} setDocs={setDocs} />
        </div>
        <div className={`${panel === "chat" ? "block" : "hidden"} min-h-0 md:block`}>
          <Chat
            docCount={docs ? docs.length : null}
            paused={flags.global_ai_master_switch === false}
            showV2={flags.rag_v2 === true}
            onUsage={refreshBilling}
            onChatError={refreshFlags}
          />
        </div>
      </main>
    </div>
  );
}