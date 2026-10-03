import { useEffect, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { verifyEmail } from "../api/auth";
import ErrorBanner from "../components/ErrorBanner";

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"working" | "done" | "failed">("working");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    verifyEmail(token)
      .then(() => !cancelled && setState("done"))
      .catch((err) => {
        if (!cancelled) {
          setError(err);
          setState("failed");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (!token) {
    return (
      <div className="page" style={{ maxWidth: 380 }}>
        <h1>QA Vision</h1>
        <div className="card">
          <p>This verification link is incomplete — it carries no token. Use the full link from the email.</p>
          <Link to="/register">Register</Link>
        </div>
      </div>
    );
  }
  if (state === "done") return <Navigate to="/" replace />;

  return (
    <div className="page" style={{ maxWidth: 380 }}>
      <h1>QA Vision</h1>
      <div className="card">
        {state === "working" && <p className="muted">Verifying your email…</p>}
        {state === "failed" && (
          <>
            {error != null && <ErrorBanner error={error} />}
            <p className="muted">
              Verification links expire and work only once. Register again to get a fresh one.
            </p>
            <Link to="/register">Register</Link>
          </>
        )}
      </div>
    </div>
  );
}
