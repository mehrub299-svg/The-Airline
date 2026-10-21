import { useEffect, useRef, useState } from "react";
import Tip from "./Tip.jsx";

function PinIcon({ filled }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 17v5" />
      <path d="M9 3h6l-1 6 3 3v2H7v-2l3-3-1-6z" />
    </svg>
  );
}

function HideIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16" />
      <path d="M16 10l-2 2 2 2" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 6h18" />
      <path d="M8 6V4h8v2" />
      <path d="M6 6l1 14h10l1-14" />
    </svg>
  );
}

function ChatRow({ chat, active, pinned, onSelect, onTogglePin, onDelete }) {
  const [confirming, setConfirming] = useState(false);

  if (confirming) {
    return (
      <li>
        <div className="flex items-center justify-between gap-2 rounded-lg bg-page px-3 py-2 text-sm">
          <span className="truncate">Delete this chat?</span>
          <span className="shrink-0 space-x-3 text-xs font-semibold">
            <button
              onClick={() => {
                setConfirming(false);
                onDelete(chat.id);
              }}
              className="text-alert underline"
            >
              Delete
            </button>
            <button onClick={() => setConfirming(false)} className="text-muted underline">
              Cancel
            </button>
          </span>
        </div>
      </li>
    );
  }

  return (
    <li>
      <div className={`group flex items-center gap-1 rounded-lg ${active ? "bg-page" : "hover:bg-page"}`}>
        <button
          onClick={() => onSelect(chat.id)}
          aria-current={active ? "true" : undefined}
          title={chat.title}
          className={`min-w-0 flex-1 truncate px-3 py-2 text-left text-sm ${active ? "font-semibold" : ""}`}
        >
          {chat.title}
        </button>
        <button
          onClick={() => onTogglePin(chat.id)}
          aria-label={pinned ? "Unpin chat" : "Pin chat"}
          aria-pressed={pinned}
          className={`rounded p-1.5 text-muted hover:text-ink ${
            pinned ? "" : "opacity-60 focus:opacity-100 group-hover:opacity-100"
          }`}
        >
          <PinIcon filled={pinned} />
        </button>
        <button
          onClick={() => setConfirming(true)}
          aria-label="Delete chat"
          className="mr-1 rounded p-1.5 text-muted opacity-60 hover:text-alert focus:opacity-100 group-hover:opacity-100"
        >
          <TrashIcon />
        </button>
      </div>
    </li>
  );
}

export default function Sidebar({
  chats,
  activeChatId,
  pinned,
  onSelect,
  onTogglePin,
  onDelete,
  onNewChat,
  onHide,
  user,
  billing,
  onOpenSettings,
  onSignOut,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const footerRef = useRef(null);

  // Close the account menu when clicking elsewhere or pressing Escape.
  useEffect(() => {
    if (!menuOpen) return;
    const onPointerDown = (event) => {
      if (footerRef.current && !footerRef.current.contains(event.target)) setMenuOpen(false);
    };
    const onKey = (event) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const pinnedChats = chats.filter((c) => pinned.has(c.id));
  const recentChats = chats.filter((c) => !pinned.has(c.id));
  const isPro = billing?.plan_tier === "PRO";
  const initial = (user.email || "?").charAt(0).toUpperCase();

  const renderRows = (list) =>
    list.map((chat) => (
      <ChatRow
        key={chat.id}
        chat={chat}
        active={chat.id === activeChatId}
        pinned={pinned.has(chat.id)}
        onSelect={onSelect}
        onTogglePin={onTogglePin}
        onDelete={onDelete}
      />
    ));

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 px-4 pt-4">
        <p className="wordmark text-[1.6rem] text-ink">THE AIRLINE</p>
        <Tip label="Hide sidebar" align="right">
          <button
            onClick={onHide}
            aria-label="Hide sidebar"
            className="rounded-lg p-2 text-muted hover:bg-page hover:text-ink"
          >
            <HideIcon />
          </button>
        </Tip>
      </div>

      <div className="px-3 pt-4">
        <button
          onClick={onNewChat}
          className="w-full rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-onbrand hover:bg-brand-hover"
        >
          Start new chat
        </button>
      </div>

      <nav aria-label="Chats" className="mt-4 min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {chats.length === 0 && (
          <p className="px-3 py-2 text-sm text-muted">No chats yet. Ask a question to start one.</p>
        )}

        {pinnedChats.length > 0 && (
          <section>
            <h2 className="px-3 pb-1 text-xs font-semibold text-muted">Pinned</h2>
            <ul>{renderRows(pinnedChats)}</ul>
          </section>
        )}

        {recentChats.length > 0 && (
          <section className={pinnedChats.length > 0 ? "mt-4" : ""}>
            <h2 className="px-3 pb-1 text-xs font-semibold text-muted">History</h2>
            <ul>{renderRows(recentChats)}</ul>
          </section>
        )}
      </nav>

      <div ref={footerRef} className="relative border-t border-line p-3">
        {menuOpen && (
          <div
            role="menu"
            className="absolute bottom-full left-3 right-3 z-50 mb-2 rounded-xl bg-surface p-1 shadow-lg ring-1 ring-line"
          >
            <button
              role="menuitem"
              onClick={() => {
                setMenuOpen(false);
                onOpenSettings();
              }}
              className="block w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-page"
            >
              Settings
            </button>
            <button
              role="menuitem"
              onClick={() => {
                setMenuOpen(false);
                onSignOut();
              }}
              className="block w-full rounded-lg px-3 py-2 text-left text-sm text-alert hover:bg-page"
            >
              Sign out
            </button>
          </div>
        )}

        <button
          onClick={() => setMenuOpen((open) => !open)}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          className="flex w-full items-center gap-3 rounded-xl p-2 text-left hover:bg-page"
        >
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand text-sm font-semibold text-onbrand">
            {initial}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold">{user.email}</span>
            <span className="block text-xs text-muted">
              {billing ? (isPro ? "Pro plan" : "Free plan") : "\u00a0"}
            </span>
          </span>
        </button>
      </div>
    </div>
  );
}