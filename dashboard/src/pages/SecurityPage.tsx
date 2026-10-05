import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import QRCode from "qrcode";
import { CircleCheck } from "lucide-react";
import { changePassword, mfaConfirm, mfaDisable, mfaEnroll } from "../api/auth";
import { downloadCsv } from "../lib/csv";
import ErrorBanner from "../components/ErrorBanner";
import NewPasswordFields from "../components/NewPasswordFields";

type Step = "idle" | "enrolling" | "enrolled" | "disabling";

function ChangePasswordCard() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mismatch, setMismatch] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [changed, setChanged] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setChanged(false);
    if (next !== confirm) {
      setMismatch(true);
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await changePassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      setChanged(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card form-stack" onSubmit={onSubmit}>
      <h3>Password</h3>
      <p className="muted">
        Changing it signs out every other device. Accounts that sign in with Google or
        Microsoft manage their password with that provider.
      </p>
      {error != null && <ErrorBanner error={error} />}
      {changed && (
        <p className="success-note" role="status">
          <CircleCheck size={18} aria-hidden="true" />
          <span>Password changed. Other devices have been signed out.</span>
        </p>
      )}
      <label>
        Current password
        <input
          type="password"
          required
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
      </label>
      <NewPasswordFields
        password={next}
        confirm={confirm}
        onPassword={setNext}
        onConfirm={(value) => {
          setConfirm(value);
          setMismatch(false);
        }}
        mismatch={mismatch}
      />
      <div>
        <button className="primary" type="submit" disabled={busy}>
          {busy ? "Changing…" : "Change password"}
        </button>
      </div>
    </form>
  );
}

export default function SecurityPage() {
  const [step, setStep] = useState<Step>("idle");
  const [secret, setSecret] = useState("");
  const [uri, setUri] = useState("");
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (uri && canvasRef.current) {
      QRCode.toCanvas(canvasRef.current, uri, { width: 192 }).catch(() => {
        // The secret below covers manual entry when the QR cannot render.
      });
    }
  }, [uri]);

  async function onStart() {
    setError(null);
    setBusy(true);
    try {
      const enrollment = await mfaEnroll();
      setSecret(enrollment.secret);
      setUri(enrollment.otpauth_uri);
      setStep("enrolling");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await mfaConfirm(code.trim());
      setRecovery(result.recovery_codes);
      setStep("enrolled");
      setCode("");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function onDisable(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await mfaDisable(code.trim());
      setStep("idle");
      setSecret("");
      setUri("");
      setCode("");
      setRecovery(null);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 560 }}>
      <div className="page-header">
        <h1>Security</h1>
        <Link to="/">Back to projects</Link>
      </div>
      <h2 className="sr-only">Sign-in settings</h2>
      <ChangePasswordCard />
      <div className="card">
        <h3>Two-factor authentication (TOTP)</h3>
        {error != null && <ErrorBanner error={error} />}

        {step === "idle" && (
          <>
            <p className="muted">
              Adds an authenticator-app code to your password sign-in. SSO
              sign-ins keep their provider's own MFA.
            </p>
            <button className="primary" onClick={onStart} disabled={busy}>
              Set up two-factor authentication
            </button>
            <p style={{ marginTop: 16 }}>
              Already enabled on this account?{" "}
              <button onClick={() => setStep("disabling")}>Disable it</button>
            </p>
          </>
        )}

        {step === "enrolling" && (
          <form onSubmit={onConfirm}>
            <p>Scan the QR code with your authenticator app, or enter the secret manually:</p>
            <canvas ref={canvasRef} />
            <p>
              <code>{secret}</code>
            </p>
            <p>
              <label>
                Code from the app
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  autoComplete="one-time-code"
                  required
                />
              </label>
            </p>
            <button className="primary" type="submit" disabled={busy}>
              Confirm
            </button>
          </form>
        )}

        {step === "enrolled" && recovery && (
          <>
            <p>
              Two-factor authentication is on. These recovery codes are shown
              only once — store them somewhere safe. Each works a single time
              if you lose the authenticator.
            </p>
            <ul>
              {recovery.map((c) => (
                <li key={c}>
                  <code>{c}</code>
                </li>
              ))}
            </ul>
            <button onClick={() => downloadCsv("qa-vision-recovery-codes.txt", recovery.join("\n"))}>
              Download codes
            </button>
          </>
        )}

        {step === "disabling" && (
          <form onSubmit={onDisable}>
            <p>
              <label>
                Current code (or a recovery code)
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  autoComplete="one-time-code"
                  required
                />
              </label>
            </p>
            <button className="primary" type="submit" disabled={busy}>
              Disable two-factor authentication
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
