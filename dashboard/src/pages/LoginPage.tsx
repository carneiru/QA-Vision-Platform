import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { login, mfaVerify, ssoLogin } from "../api/auth";
import {
  getMicrosoftCredential,
  googleEnabled,
  initGoogleButton,
  microsoftEnabled,
} from "../auth/ssoProviders";
import { safeNext } from "../auth/redirect";
import ErrorBanner from "../components/ErrorBanner";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  // Back to the page the user asked for (validated: same-origin paths only), else the front page
  const next = safeNext(params.get("next")) ?? "/";
  const expired = params.get("reason") === "expired";
  const googleRef = useRef<HTMLDivElement>(null);

  async function finishSso(provider: "google" | "microsoft", credential: string) {
    setError(null);
    try {
      await ssoLogin(provider, credential);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => {
    if (googleEnabled() && googleRef.current) {
      initGoogleButton(googleRef.current, (credential) => {
        void finishSso("google", credential);
      }).catch((err) => setError(err));
    }
    // Mount-only: the google button renders once into the ref.
  }, []);

  async function onMicrosoft() {
    setError(null);
    try {
      const credential = await getMicrosoftCredential();
      await finishSso("microsoft", credential);
    } catch (err) {
      setError(err);
    }
  }

  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const challenge = await login(email, password);
      if (challenge) {
        setMfaToken(challenge.mfaToken);
        return;
      }
      navigate(next, { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function onMfaSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await mfaVerify(mfaToken!, mfaCode.trim());
      navigate(next, { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (mfaToken !== null) {
    return (
      <div className="page page-narrow">
        <h1>QEOS</h1>
        <p className="brand-subtitle">Quality Engineering OS</p>
        <form className="card" onSubmit={onMfaSubmit}>
          <p>Enter the code from your authenticator app, or a recovery code.</p>
          <p>
            <label>
              Authentication code
              <input
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
                autoComplete="one-time-code"
                autoFocus
                required
              />
            </label>
          </p>
          {error != null && <ErrorBanner error={error} />}
          <button className="primary" type="submit" disabled={busy}>
            {busy ? "Verifying…" : "Verify"}
          </button>
        </form>
      </div>
    );
  }

  const anySso = googleEnabled() || microsoftEnabled();

  return (
    <div className="page page-narrow">
      <h1>QEOS</h1>
      <p className="brand-subtitle">Quality Engineering OS</p>
      <form className="card" onSubmit={onSubmit}>
        {expired && <p role="status" className="muted">Your session expired, sign in again.</p>}
        <p>
          <label>
            Email
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
        </p>
        <p>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
        </p>
        {/* Router state, not a query string: an address in the URL ends up in history and access logs */}
        <Link className="field-link" to="/forgot-password" state={{ email }}>
          Forgot password?
        </Link>
        {error != null && <ErrorBanner error={error} />}
        <button className="primary" type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        {anySso && (
          <>
            <p className="muted" style={{ textAlign: "center", margin: "16px 0 8px" }}>
              or
            </p>
            {googleEnabled() && <div ref={googleRef} />}
            {microsoftEnabled() && (
              <button type="button" onClick={onMicrosoft} style={{ width: "100%", marginTop: 8 }}>
                Sign in with Microsoft
              </button>
            )}
          </>
        )}
        <p className="muted" style={{ marginBottom: 0 }}>
          New here? <Link to="/register">Create account</Link>
        </p>
      </form>
    </div>
  );
}
