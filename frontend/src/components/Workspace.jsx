import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import ChatPanel from "./ChatPanel.jsx";
import DocumentsPanel from "./DocumentsPanel.jsx";
import SettingsDialog from "./SettingsDialog.jsx";
import Sidebar from "./Sidebar.jsx";
import Tip from "./Tip.jsx";

const fmt = (n) => new Intl.NumberFormat().format(n);
const PINS_KEY = "airline.pins";
const PANELS_KEY = "airline.panels";
const isWide = () => window.matchMedia("(min-width: 768px)").matches;
const countText = (n) => `${n} ${n === 1 ? "document" : "documents"}`;

function loadPins() {
  try {
    return new Set(JSON.parse(localStorage.getItem(PINS_KEY)) || []);
  } catch {
    return new Set();
  }
}

function loadPanels() {
  try {
    return JSON.parse(localStorage.getItem(PANELS_KEY)) || {};
  } catch {
    return {};
  }
}

function SidebarIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16" />
    </svg>
  );
}

function FilesIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
    </svg>
  );
}

// A side panel that slides in and out. On phones it is a drawer over the page; on computers it
// sits in the row and its width animates to zero, so the chat area grows to fill the space.
function SidePanel({ open, side, children }) {
  const left = side === "left";
  const base =
    "fixed inset-y-0 z-30 flex min-h-0 max-w-[88vw] flex-col overflow-hidden bg-surface shadow-xl " +
    "md:static md:z-auto md:max-w-none md:shrink-0 md:transform-none md:rounded-2xl md:shadow-none " +
    "motion-reduce:[transition:none]";
  const placement = left ? "left-0 w-72" : "right-0 w-80";
  const openState = left
    ? "visible translate-x-0 md:mr-4 md:ring-1 md:ring-line [transition:transform_200ms_ease-out,width_200ms_ease-out,margin_200ms_ease-out]"
    : "visible translate-x-0 md:ml-4 md:ring-1 md:ring-line [transition:transform_200ms_ease-out,width_200ms_ease-out,margin_200ms_ease-out]";
  const closedState = left
    ? "invisible -translate-x-full md:w-0 [transition:transform_200ms_ease-out,width_200ms_ease-out,margin_200ms_ease-out,visibility_0s_linear_200ms]"
    : "invisible translate-x-full md:w-0 [transition:transform_200ms_ease-out,width_200ms_ease-out,margin_200ms_ease-out,visibility_0s_linear_200ms]";

  return (
    <aside
      aria-hidden={!open}
      className={`${base} ${placement} ${open ? openState : closedState}`}
    >
      <div className={`min-h-0 flex-1 ${left ? "w-72" : "w-80"}`}>{children}</div>
    </aside>
  );
}

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
  const [chats, setChats] = useState([]);
  const [unselected, setUnselected] = useState(new Set());
  const [pinned, setPinned] = useState(loadPins);
  const [activeChatId, setActiveChatId] = useState(null);
  const [viewKey, setViewKey] = useState(0);
  const [leftOpen, setLeftOpen] = useState(() => (isWide() ? loadPanels().left !== false : false));
  const [rightOpen, setRightOpen] = useState(() => (isWide() ? loadPanels().right !== false : false));
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [useV2, setUseV2] = useState(false);
  const [notice, setNotice] = useState(initialNotice ? { tone: "info", text: initialNotice } : null);
  const [upgrading, setUpgrading] = useState(false);

  // Remember which panels are open (computers only; on phones they are temporary drawers).
  useEffect(() => {
    if (!isWide()) return;
    try {
      localStorage.setItem(PANELS_KEY, JSON.stringify({ left: leftOpen, right: rightOpen }));
    } catch {
      // not remembered this time
    }
  }, [leftOpen, rightOpen]);

  const refreshChats = useCallback(async () => {
    try {
      setChats(await api.listChats());
    } catch {
      // keep the list we already have
    }
  }, []);

  useEffect(() => {
    refreshChats();
    api
      .documents()
      .then(setDocs)
      .catch((err) => {
        setDocs([]);
        setNotice({ tone: "error", text: `Couldn't load your documents. ${err.message}` });
      });
  }, [refreshChats]);

  const isPro = billing?.plan_tier === "PRO";
  const used = billing?.monthly_tokens_used ?? 0;
  const limit = billing?.monthly_token_limit ?? 0;
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;

  const docList = docs || [];
  const selectedDocs = docList.filter((d) => !unselected.has(d.id));
  const allSelected = selectedDocs.length === docList.length;
  const documentIds = allSelected ? null : selectedDocs.map((d) => d.id);

  const paused = flags.global_ai_master_switch === false;
  const showV2 = flags.rag_v2 === true;

  let lockedMessage = null;
  if (paused) lockedMessage = "Chat is paused for maintenance.";
  else if (docs && docList.length === 0) lockedMessage = "Upload a document to start asking questions.";
  else if (docs && selectedDocs.length === 0) lockedMessage = "Select at least one document to ask about.";

  let scopeText = "";
  if (docs && docList.length > 0) {
    scopeText = allSelected
      ? `Answering from all ${countText(docList.length)}.`
      : `Answering from ${selectedDocs.length} of ${countText(docList.length)}.`;
  }

  const activeTitle = chats.find((c) => c.id === activeChatId)?.title || "New chat";

  function openChat(id) {
    setActiveChatId(id);
    setViewKey((k) => k + 1);
    if (!isWide()) setLeftOpen(false);
  }

  function newChat() {
    setActiveChatId(null);
    setViewKey((k) => k + 1);
    if (!isWide()) setLeftOpen(false);
  }

  function togglePin(id) {
    const next = new Set(pinned);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setPinned(next);
    try {
      localStorage.setItem(PINS_KEY, JSON.stringify([...next]));
    } catch {
      // pins just won't persist
    }
  }

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

  const leftLabel = leftOpen ? "Hide sidebar" : "Show sidebar";
  const rightLabel = rightOpen ? "Hide documents" : "Show documents";

  return (
    <div className="flex h-dvh flex-col">
      <header className="px-3 pt-3 md:px-5 md:pt-4">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Tip label={leftLabel}>
            <button
              onClick={() => setLeftOpen((open) => !open)}
              aria-label={leftLabel}
              aria-expanded={leftOpen}
              className="rounded-lg p-2 hover:bg-surface"
            >
              <SidebarIcon />
            </button>
          </Tip>
          <h1 className="min-w-0 flex-1 truncate font-display text-lg font-bold">{activeTitle}</h1>

          <div className="flex flex-wrap items-center gap-3 md:gap-4">
            {billing && (
              <div className="min-w-[10rem]">
                <div className="flex justify-between text-xs text-muted">
                  <span>Token usage</span>
                  <span>
                    {fmt(used)} of {fmt(limit)}
                  </span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-line/70">
                  <div
                    className={`h-full rounded-full ${pct >= 90 ? "bg-alert" : "bg-brand"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            )}

            {billing && (
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  isPro ? "bg-signal text-ink" : "bg-line/70"
                }`}
              >
                {isPro ? "Pro" : "Free"}
              </span>
            )}

            {billing && !isPro && (
              <button
                onClick={upgrade}
                disabled={upgrading}
                className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-onbrand hover:bg-brand-hover disabled:opacity-60"
              >
                {upgrading ? "Upgrading…" : "Upgrade to Pro"}
              </button>
            )}

            <Tip label={rightLabel} align="right">
              <button
                onClick={() => setRightOpen((open) => !open)}
                aria-label={rightLabel}
                aria-expanded={rightOpen}
                className="flex items-center gap-2 rounded-lg p-2 text-sm font-semibold hover:bg-surface"
              >
                <FilesIcon />
                <span className="hidden sm:inline">Documents</span>
              </button>
            </Tip>
          </div>
        </div>
        <div className="runway mt-3" aria-hidden="true" />
      </header>

      {notice && (
        <div
          role={notice.tone === "error" ? "alert" : "status"}
          className={`mx-3 mt-3 flex items-start justify-between gap-4 rounded-lg px-4 py-3 text-sm md:mx-5 ${
            notice.tone === "error" ? "bg-alert/10 text-alert" : "bg-surface ring-1 ring-line"
          }`}
        >
          <span>{notice.text}</span>
          <button onClick={() => setNotice(null)} className="shrink-0 font-semibold underline">
            Dismiss
          </button>
        </div>
      )}

      {leftOpen && (
        <button
          aria-label="Hide sidebar"
          onClick={() => setLeftOpen(false)}
          className="fixed inset-0 z-20 bg-ink/40 md:hidden"
        />
      )}
      {rightOpen && (
        <button
          aria-label="Hide documents"
          onClick={() => setRightOpen(false)}
          className="fixed inset-0 z-20 bg-ink/40 md:hidden"
        />
      )}

      <div className="flex min-h-0 flex-1 md:px-5 md:pb-5 md:pt-4">
        <SidePanel open={leftOpen} side="left">
          <Sidebar
            chats={chats}
            activeChatId={activeChatId}
            pinned={pinned}
            onSelect={openChat}
            onTogglePin={togglePin}
            onNewChat={newChat}
            onHide={() => setLeftOpen(false)}
            user={user}
            billing={billing}
            onOpenSettings={() => setSettingsOpen(true)}
            onSignOut={onSignOut}
          />
        </SidePanel>

        <main className="min-w-0 flex-1 px-3 pb-3 pt-3 md:p-0">
          <div className="h-full min-h-0 rounded-2xl bg-surface ring-1 ring-line">
            <ChatPanel
              key={viewKey}
              initialChatId={activeChatId}
              documentIds={documentIds}
              lockedMessage={lockedMessage}
              paused={paused}
              scopeText={scopeText}
              useV2={showV2 && useV2}
              onChatCreated={setActiveChatId}
              onChatsChanged={refreshChats}
              onUsage={refreshBilling}
              onChatError={refreshFlags}
            />
          </div>
        </main>

        <SidePanel open={rightOpen} side="right">
          <DocumentsPanel
            docs={docs}
            setDocs={setDocs}
            unselected={unselected}
            setUnselected={setUnselected}
            onClose={() => setRightOpen(false)}
          />
        </SidePanel>
      </div>

      {settingsOpen && (
        <SettingsDialog
          user={user}
          billing={billing}
          showV2={showV2}
          useV2={useV2}
          onUseV2={setUseV2}
          onClose={() => setSettingsOpen(false)}
        />
      )}
    </div>
  );
}