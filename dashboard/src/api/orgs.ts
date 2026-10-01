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

export function listMyOrganizations(): Promise<MyOrganization[]> {
  return apiFetch("/api/v1/organizations");
}

export function listProjects(orgId: number): Promise<Project[]> {
  return apiFetch(`/api/v1/organizations/${orgId}/projects`);
}
