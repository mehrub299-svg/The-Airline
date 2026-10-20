import { useState } from "react";
import { api } from "../api.js";

const inputClass =
  "w-full rounded-lg border border-line bg-surface px-4 py-3 text-ink placeholder:text-muted/60";
const labelClass = "mb-1.5 block text-sm font-semibold text-ink";

export default function AuthScreen({ onAuthed }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await api.login(email.trim(), password);
      await onAuthed();
    } catch (err) {
      setError(
        err.retryAfter
          ? `${err.message} Try again in about ${Math.ceil(err.retryAfter / 60)} minutes.`
          : err.message
      );
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
          <h2 className="font-display text-2xl font-bold text-ink">Sign in</h2>

          <form onSubmit={submit} className="mt-6 space-y-5">
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
                maxLength={128}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
              />
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
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="mt-6 text-sm text-muted">
            Accounts are created by your administrator. If you don't have one yet, ask them to set one up.
          </p>
        </section>
      </div>
    </main>
  );
}