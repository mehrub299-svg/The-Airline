import "./theme.js";
import { useCallback, useEffect, useState } from "react";
import { api, clearTokens, hasSession } from "./api.js";
import AuthScreen from "./components/AuthScreen.jsx";
import Workspace from "./components/Workspace.jsx";

export default function App() {
  const [booting, setBooting] = useState(hasSession());
  const [user, setUser] = useState(null);
  const [flags, setFlags] = useState({});
  const [billing, setBilling] = useState(null);
  const [notice, setNotice] = useState("");

  const refreshBilling = useCallback(async () => {
    try {
      setBilling(await api.billingStatus());
    } catch {
      // keep the last known value
    }
  }, []);

  const refreshFlags = useCallback(async () => {
    try {
      setFlags(await api.flags());
    } catch {
      // keep the last known value
    }
  }, []);

  const enter = useCallback(async () => {
    setUser(await api.me());
    await Promise.all([refreshBilling(), refreshFlags()]);
  }, [refreshBilling, refreshFlags]);

  // Restore an existing session.
  useEffect(() => {
    if (!hasSession()) return;
    (async () => {
      try {
        await enter();
      } catch {
        clearTokens();
      } finally {
        setBooting(false);
      }
    })();
  }, [enter]);

  // Returning from Stripe Checkout.
  useEffect(() => {
    const result = new URLSearchParams(window.location.search).get("checkout");
    if (!result) return;
    setNotice(
      result === "success"
        ? "Payment submitted. Your plan updates as soon as Stripe confirms it."
        : "Checkout cancelled. No charge was made."
    );
    window.history.replaceState({}, "", window.location.pathname);
  }, []);

  // The API layer fires this when a refresh token is rejected.
  useEffect(() => {
    const onSignOut = () => {
      setUser(null);
      setBilling(null);
    };
    window.addEventListener("airline:signout", onSignOut);
    return () => window.removeEventListener("airline:signout", onSignOut);
  }, []);

  async function signOut() {
    await api.logout();
    setUser(null);
    setBilling(null);
    setFlags({});
    setNotice("");
  }

  if (booting) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <p className="wordmark text-3xl text-navy">THE AIRLINE</p>
      </div>
    );
  }

  return user ? (
    <Workspace
      user={user}
      flags={flags}
      billing={billing}
      initialNotice={notice}
      refreshBilling={refreshBilling}
      refreshFlags={refreshFlags}
      onSignOut={signOut}
    />
  ) : (
    <AuthScreen onAuthed={enter} />
  );
}