import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { register } from "../api/auth";
import ErrorBanner from "../components/ErrorBanner";

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register(email, password, fullName);
      setDone(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="page page-narrow">
        <h1>QEOS</h1>
        <p className="brand-subtitle">Quality Engineering OS</p>
        <div className="card">
          <p role="status">Check your email to complete registration.</p>
          <p className="muted">
            If no email arrives, this deployment has no mail server configured: ask your
            administrator for the verification link (it appears in the auth service's log).
          </p>
          <Link to="/login">Back to sign in</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page page-narrow">
      <h1>QEOS</h1>
      <p className="brand-subtitle">Quality Engineering OS</p>
      <form className="card" onSubmit={onSubmit}>
        <h2>Create account</h2>
        {error != null && <ErrorBanner error={error} />}
        <label>
          Full name
          <input autoComplete="name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </label>
        <label>
          Email
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button className="primary" type="submit" disabled={busy}>
          Create account
        </button>
        <p className="muted" style={{ marginBottom: 0 }}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
