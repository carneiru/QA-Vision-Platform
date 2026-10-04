import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  InvitationCreated, ROLES, createInvitation, listInvitations, listMembers,
  listMyOrganizations, myRole, removeMember, revokeInvitation,
} from "../api/orgs";
import ConfirmButton from "../components/ConfirmButton";
import ErrorBanner from "../components/ErrorBanner";

const MANAGER_ROLES = ["owner", "admin"];

export default function OrganizationPage() {
  const { orgId } = useParams();
  const id = Number(orgId);
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [created, setCreated] = useState<InvitationCreated | null>(null);
  const [notice, setNotice] = useState("");
  const [copied, setCopied] = useState(false);

  async function copyInviteLink(link: string) {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      setCopied(false); // clipboard blocked (permissions, http): the link stays selectable
    }
  }

  const orgs = useQuery({ queryKey: ["orgs"], queryFn: listMyOrganizations });
  const me = useQuery({ queryKey: ["org", id, "me"], queryFn: () => myRole(id) });
  const members = useQuery({ queryKey: ["org", id, "members"], queryFn: () => listMembers(id) });
  const invitations = useQuery({ queryKey: ["org", id, "invitations"], queryFn: () => listInvitations(id) });

  const canManage = me.data != null && MANAGER_ROLES.includes(me.data.role);
  const org = orgs.data?.find((o) => o.id === id);

  const invite = useMutation({
    mutationFn: () => createInvitation(id, email, role),
    onSuccess: (invitation) => {
      setCreated(invitation);
      setCopied(false);
      setEmail("");
      setNotice("");
      qc.invalidateQueries({ queryKey: ["org", id, "invitations"] });
    },
  });
  const revoke = useMutation({
    mutationFn: (invitationId: number) => revokeInvitation(id, invitationId),
    onSuccess: () => {
      setNotice("Invitation revoked.");
      qc.invalidateQueries({ queryKey: ["org", id, "invitations"] });
    },
  });
  const remove = useMutation({
    mutationFn: (memberId: number) => removeMember(id, memberId),
    onSuccess: () => {
      setNotice("Member removed.");
      qc.invalidateQueries({ queryKey: ["org", id, "members"] });
    },
  });

  const error = orgs.error ?? me.error ?? members.error ?? invitations.error;
  const pending = invitations.data?.filter((i) => i.accepted_at === null) ?? [];

  return (
    <div className="page">
      <div className="page-header">
        <h1>{org?.name ?? `Organization ${id}`}</h1>
        <Link to="/">Choose a project</Link>
      </div>
      {error != null && <ErrorBanner error={error} onRetry={() => members.refetch()} />}
      {(invite.error ?? revoke.error ?? remove.error) != null && (
        <ErrorBanner error={(invite.error ?? revoke.error ?? remove.error)!} />
      )}
      {notice && <p role="status">{notice}</p>}

      <div className="card">
        <h2>Members</h2>
        {members.isPending && <p className="muted">Loading members…</p>}
        {members.data && (
          <table className="data">
            <thead>
              <tr>
                <th>User</th><th>Role</th><th>Status</th><th>Since</th>
                {canManage && <th><span className="sr-only">Actions</span></th>}
              </tr>
            </thead>
            <tbody>
              {members.data.map((member) => (
                <tr key={member.id}>
                  <td>{member.email ?? `user ${member.user_id}`}</td>
                  <td>{member.role}</td>
                  <td>{member.status}</td>
                  <td>{new Date(member.created_at).toLocaleDateString()}</td>
                  {canManage && (
                    <td>
                      <ConfirmButton
                        label="Remove"
                        ariaLabel={`Remove ${member.email ?? `user ${member.user_id}`}`}
                        question={`Remove ${member.email ?? `user ${member.user_id}`}? They lose access to every project in this organization.`}
                        confirmLabel="Remove"
                        onConfirm={() => remove.mutate(member.id)}
                        disabled={remove.isPending}
                      />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>Invitations</h2>
        {canManage && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              invite.mutate();
            }}
            className="inline-form"
          >
            <label>
              Email
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label>
              Role
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                {ROLES.filter((r) => r !== "owner").map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </label>
            <button type="submit" disabled={invite.isPending}>Invite</button>
          </form>
        )}
        {created && (
          <p role="status">
            Invitation for <strong>{created.email}</strong> — send this link (only shown once):{" "}
            <code>{`${window.location.origin}/invitations/${created.token}`}</code>{" "}
            <button
              aria-label={`Copy the invitation link for ${created.email}`}
              onClick={() => copyInviteLink(`${window.location.origin}/invitations/${created.token}`)}
            >
              {copied ? "Copied" : "Copy link"}
            </button>
          </p>
        )}
        {invitations.isPending && <p className="muted">Loading invitations…</p>}
        {pending.length === 0 && invitations.data && <p className="muted">No pending invitations.</p>}
        {pending.length > 0 && (
          <table className="data">
            <thead>
              <tr>
                <th>Email</th><th>Role</th><th>Expires</th>
                {canManage && <th><span className="sr-only">Actions</span></th>}
              </tr>
            </thead>
            <tbody>
              {pending.map((invitation) => (
                <tr key={invitation.id}>
                  <td>{invitation.email}</td>
                  <td>{invitation.role}</td>
                  <td>{new Date(invitation.expires_at).toLocaleDateString()}</td>
                  {canManage && (
                    <td>
                      <ConfirmButton
                        label="Revoke"
                        ariaLabel={`Revoke invitation for ${invitation.email}`}
                        question={`Revoke the invitation for ${invitation.email}? The link stops working.`}
                        confirmLabel="Revoke"
                        onConfirm={() => revoke.mutate(invitation.id)}
                        disabled={revoke.isPending}
                      />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
