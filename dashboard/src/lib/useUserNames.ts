import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { getProject, listMembers } from "../api/orgs";

/** A person's name for "started by", "stopped by" and "last changed by": their email from the
 *  organization's members, or "user #<id>" while it loads or when it is unknown. */
export function useUserNames(projectId: number): (userId: number | null) => string {
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => getProject(projectId) });
  const orgId = project.data?.organization_id;
  const members = useQuery({
    queryKey: ["org", orgId, "members"],
    queryFn: () => listMembers(orgId as number),
    enabled: orgId != null,
    staleTime: 5 * 60_000,
  });
  return useCallback(
    (userId: number | null) => {
      if (userId == null) return "someone";
      return members.data?.find((m) => m.user_id === userId)?.email ?? `user #${userId}`;
    },
    [members.data],
  );
}
