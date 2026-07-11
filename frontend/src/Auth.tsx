import { useState } from "react";
import { api, setToken, type User } from "./api";

export default function Auth({ onAuthed }: { onAuthed: (user: User) => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = mode === "login" ? await api.login(email, password) : await api.signup(email, password);
      setToken(result.token);
      onAuthed(result.user);
    } catch (err) {
      const msg = (err as Error).message.replace(/^\d+:\s*/, "");
      setError(msg || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="logo">📖</span>
          <h1>Study Helper</h1>
          <p className="tagline">Turn your notes into an adventure</p>
        </div>

        <div className="auth-tabs">
          <button
            type="button"
            className={"auth-tab" + (mode === "login" ? " active" : "")}
            onClick={() => {
              setMode("login");
              setError(null);
            }}
          >
            Log in
          </button>
          <button
            type="button"
            className={"auth-tab" + (mode === "signup" ? " active" : "")}
            onClick={() => {
              setMode("signup");
              setError(null);
            }}
          >
            Create account
          </button>
        </div>

        <form className="auth-form" onSubmit={submit}>
          <label className="auth-label">
            Email
            <input
              className="text-input"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="auth-label">
            Password
            <input
              className="text-input"
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {mode === "signup" && <p className="auth-hint">At least 8 characters.</p>}
          {error && <div className="notice warn">{error}</div>}
          <button className="btn auth-submit" type="submit" disabled={busy}>
            {busy ? "…" : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}
