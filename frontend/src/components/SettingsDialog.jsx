import { useEffect, useState } from "react";
import { getTheme, setTheme } from "../theme.js";

const THEMES = [
  ["light", "Light"],
  ["dark", "Dark"],
  ["system", "System"],
];

export default function SettingsDialog({ user, billing, showV2, useV2, onUseV2, onClose }) {
  const [theme, setThemeState] = useState(getTheme());
  const isPro = billing?.plan_tier === "PRO";

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function choose(mode) {
    setTheme(mode);
    setThemeState(mode);
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <button aria-label="Close settings" onClick={onClose} className="absolute inset-0 bg-ink/50" />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        className="relative w-full max-w-md rounded-2xl bg-surface p-6 shadow-xl ring-1 ring-line"
      >
        <div className="flex items-center justify-between">
          <h2 id="settings-title" className="font-display text-xl font-bold">
            Settings
          </h2>
          <button onClick={onClose} className="text-sm font-semibold text-muted underline">
            Close
          </button>
        </div>

        <section className="mt-6">
          <h3 className="text-sm font-semibold">Theme</h3>
          <div className="mt-2 flex rounded-full bg-page p-1" role="group" aria-label="Theme">
            {THEMES.map(([id, label]) => (
              <button
                key={id}
                aria-pressed={theme === id}
                onClick={() => choose(id)}
                className={`flex-1 rounded-full py-2 text-sm font-semibold ${
                  theme === id ? "bg-brand text-onbrand" : "text-muted"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </section>

        {showV2 && (
          <section className="mt-6">
            <label className="flex items-center justify-between gap-4 text-sm">
              <span>
                <span className="font-semibold">RAG v2</span>
                <span className="block text-muted">Retrieves more passages for each question.</span>
              </span>
              <input
                type="checkbox"
                checked={useV2}
                onChange={(e) => onUseV2(e.target.checked)}
                className="h-5 w-5"
              />
            </label>
          </section>
        )}

        <section className="mt-6">
          <h3 className="text-sm font-semibold">Account</h3>
          <dl className="mt-2 space-y-1 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted">Email</dt>
              <dd className="truncate">{user.email}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">Plan</dt>
              <dd>{billing ? (isPro ? "Pro" : "Free") : "—"}</dd>
            </div>
          </dl>
        </section>
      </div>
    </div>
  );
}