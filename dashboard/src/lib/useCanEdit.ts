import { useQuery } from "@tanstack/react-query";
import { getProject } from "../api/orgs";

// Mirrors EDIT_ROLES in the services' api/deps.py
const EDIT_ROLES = ["owner", "admin", "member"];

/** Whether the signed-in person may change this project's data; undefined while the role loads. */
export function useCanEdit(projectId: number): boolean | undefined {
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => getProject(projectId) });
  return project.data == null ? undefined : EDIT_ROLES.includes(project.data.my_role ?? "");
}
