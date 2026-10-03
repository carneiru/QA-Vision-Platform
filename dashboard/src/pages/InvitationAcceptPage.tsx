import { Link, useParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { acceptInvitation } from "../api/orgs";
import ErrorBanner from "../components/ErrorBanner";

export default function InvitationAcceptPage() {
  const { token } = useParams();

  const accept = useMutation({ mutationFn: () => acceptInvitation(token ?? "") });

  return (
    <div className="page" style={{ maxWidth: 480, margin: "48px auto" }}>
      <div className="card">
        <h1>Organization invitation</h1>
        {accept.isSuccess ? (
          <>
            <p role="status">You joined the organization as <strong>{accept.data.role}</strong>.</p>
            <Link to="/">Choose a project</Link>
          </>
        ) : (
          <>
            <p className="muted">
              Accepting adds this account to the organization that invited you.
            </p>
            {accept.error != null && <ErrorBanner error={accept.error} />}
            <button onClick={() => accept.mutate()} disabled={accept.isPending}>
              Accept invitation
            </button>
          </>
        )}
      </div>
    </div>
  );
}
