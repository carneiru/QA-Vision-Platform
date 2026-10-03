import { apiFetch } from "./http";

export interface MyOrganization {
  id: number;
  name: string;
  slug: string;
  role: string;
}

export interface Project {
  id: number;
  name: string;
}

export interface Member {
  id: number;
  organization_id: number;
  user_id: number;
  email: string | null; // enriched from auth-service, best effort
  role: string;
  status: string;
  created_at: string;
  updated_at: string | null;
}

export interface InvitationPreview {
  organization_id: number;
  organization_name: string;
  email: string;
  role: string;
  expires_at: string;
}

export function previewInvitation(token: string): Promise<InvitationPreview> {
  return apiFetch(`/api/v1/invitations/${encodeURIComponent(token)}`);
}

export interface InvitationSummary {
  id: number;
  organization_id: number;
  email: string;
  role: string;
  invited_by_user_id: number;
  expires_at: string;
  created_at: string;
  accepted_at: string | null;
}

// The raw token is returned only by the create call, never by the list
export interface InvitationCreated extends InvitationSummary {
  token: string;
}

export const ROLES = ["owner", "admin", "member", "viewer", "billing_manager"] as const;

export function listMyOrganizations(): Promise<MyOrganization[]> {
  return apiFetch("/api/v1/organizations");
}

export function listMembers(orgId: number): Promise<Member[]> {
  return apiFetch(`/api/v1/organizations/${orgId}/members`);
}

export function myRole(orgId: number): Promise<{ role: string }> {
  return apiFetch(`/api/v1/organizations/${orgId}/members/me`);
}

export function removeMember(orgId: number, memberId: number): Promise<void> {
  return apiFetch(`/api/v1/organizations/${orgId}/members/${memberId}`, { method: "DELETE" });
}

export function listInvitations(orgId: number): Promise<InvitationSummary[]> {
  return apiFetch(`/api/v1/organizations/${orgId}/invitations`);
}

export function createInvitation(orgId: number, email: string, role: string): Promise<InvitationCreated> {
  return apiFetch(`/api/v1/organizations/${orgId}/invitations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, role }),
  });
}

export function revokeInvitation(orgId: number, invitationId: number): Promise<void> {
  return apiFetch(`/api/v1/organizations/${orgId}/invitations/${invitationId}`, { method: "DELETE" });
}

export function acceptInvitation(token: string): Promise<Member> {
  return apiFetch(`/api/v1/invitations/${encodeURIComponent(token)}/accept`, { method: "POST" });
}

export function listProjects(orgId: number): Promise<Project[]> {
  return apiFetch(`/api/v1/organizations/${orgId}/projects`);
}

export function getProject(projectId: number): Promise<Project> {
  return apiFetch(`/api/v1/projects/${projectId}`);
}
