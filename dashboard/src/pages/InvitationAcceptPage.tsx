import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { acceptInvitation, previewInvitation } from "../api/orgs";
import { ApiError } from "../api/http";
import ErrorBanner from "../components/ErrorBanner";

export default function InvitationAcceptPage() {
  const { token } = useParams();

  const preview = useQuery({
    queryKey: ["invitation", token],
    queryFn: () => previewInvitation(token ?? ""),
  });
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const accept = useMutation({
    mutationFn: () => acceptInvitation(token ?? ""),
    onSuccess: async (membership) => {
      // The lists are cached for a minute: without this the new organization would be missing from the picker and the switcher
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["orgs"] }),
        queryClient.invalidateQueries({ queryKey: ["projects"] }),
      ]);
      navigate(`/organizations/${membership.organization_id}`);
    },
  });

  const dead = preview.error instanceof ApiError && preview.error.status === 404;

  return (
    <div className="page" style={{ maxWidth: 480, margin: "48px auto" }}>
      <div className="card">
        <h1>Organization invitation</h1>
        {dead ? (
          <p>Invitation not found — it may have expired, been revoked, or already been used.</p>
        ) : (
          <>
            {preview.isPending && <p className="muted">Loading invitation…</p>}
            {preview.error != null && !dead && (
              <ErrorBanner error={preview.error} onRetry={() => preview.refetch()} />
            )}
            {preview.data && (
              <p>
                Join <strong>{preview.data.organization_name}</strong> as{" "}
                <strong>{preview.data.role}</strong>? Accepting adds this account to the
                organization.
              </p>
            )}
            {accept.error != null && <ErrorBanner error={accept.error} />}
            {preview.data && (
              <button className="primary" onClick={() => accept.mutate()} disabled={accept.isPending}>
                {accept.isPending ? "Joining…" : "Accept invitation"}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
