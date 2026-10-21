import { useState } from "react";
import { api } from "../api.js";

const inputClass =
  "w-full rounded-lg border border-line bg-surface px-4 py-3 text-ink placeholder:text-muted/60";
const labelClass = "mb-1.5 block text-sm font-semibold text-ink";

export default function AuthScreen({ onAuthed }) {
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const registering = mode === "register";

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      if (registering) await api.register(email.trim(), password, workspace.trim());
      else await api.login(email.trim(), password);
      await onAuthed();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-dvh flex-col px-5 py-8 md:px-12 md:py-12">
      <h1 className="wordmark whitespace-nowrap text-[clamp(2.4rem,10vw,10rem)] text-ink">
        THE AIRLINE
      </h1>
      <div className="runway mt-5 md:mt-8" aria-hidden="true" />

      <div className="mt-10 grid items-start gap-10 md:mt-16 md:grid-cols-2">
        <section className="max-w-lg">
          <p className="font-display text-3xl font-bold leading-tight text-ink md:text-5xl">
            Ask your documents anything.
          </p>
          <p className="mt-5 text-lg leading-relaxed text-muted">
            Upload PDFs, Word files, text and code. Every answer is drawn only from what you uploaded.
          </p>
        </section>

        <section className="w-full max-w-md rounded-[2.75rem] bg-surface p-7 ring-8 ring-line/70 md:justify-self-end md:p-10">
          <div className="flex rounded-full bg-page p-1" role="group" aria-label="Account">
            {[
              ["signin", "Sign in"],
              ["register", "Create account"],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                aria-pressed={mode === id}
                onClick={() => {
                  setMode(id);
                  setError("");
                }}
                className={`flex-1 rounded-full py-2.5 text-sm font-semibold ${
                  mode === id ? "bg-brand text-onbrand" : "text-muted"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="mt-7 space-y-5">
            {registering && (
              <div>
                <label htmlFor="workspace" className={labelClass}>
                  Workspace name
                </label>
                <input
                  id="workspace"
                  required
                  maxLength={255}
                  value={workspace}
                  onChange={(e) => setWorkspace(e.target.value)}
                  placeholder="Your team or company"
                  className={inputClass}
                />
              </div>
            )}

            <div>
              <label htmlFor="email" className={labelClass}>
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
              />
            </div>

            <div>
              <label htmlFor="password" className={labelClass}>
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={registering ? 8 : 1}
                maxLength={128}
                autoComplete={registering ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
              />
              {registering && <p className="mt-1.5 text-xs text-muted">At least 8 characters.</p>}
            </div>

            {error && (
              <p role="alert" className="text-sm text-alert">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-xl bg-brand py-3.5 font-semibold text-onbrand hover:bg-brand-hover disabled:opacity-60"
            >
              {busy
                ? registering
                  ? "Creating account…"
                  : "Signing in…"
                : registering
                ? "Create account"
                : "Sign in"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}