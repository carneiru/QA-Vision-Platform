// Client-side checks for Settings › Run from QEOS. They mirror the server (test-management's schemas/ci.py);
// the server still decides, these only save a round trip and say what is wrong next to the field.
const REPO = /^[A-Za-z0-9-]{1,39}\/[A-Za-z0-9._-]{1,100}$/;
const WORKFLOW = /^[A-Za-z0-9._-]{1,100}\.ya?ml$/;
// Whitespace and control characters, and the characters `git check-ref-format` forbids
// eslint-disable-next-line no-control-regex
const FORBIDDEN_IN_REF = /[\u0000-\u0020\u007f~^:?*[\\]/;  // same set as schemas/ci.py BRANCH_FORBIDDEN

export function repoError(repo: string): string | null {
  return REPO.test(repo) ? null : "Use owner/name, as on github.com";
}

export function workflowError(workflow: string): string | null {
  return WORKFLOW.test(workflow) ? null : "Use the workflow's file name, ending in .yml or .yaml (letters, digits, . _ -)";
}

/** git branch-name rules, as `git check-ref-format --branch` applies them. */
export function branchError(ref: string): string | null {
  if (ref === "") return "Enter a branch";
  if (ref.length > 255) return "A branch name has at most 255 characters";
  if (FORBIDDEN_IN_REF.test(ref)) return "A branch name cannot hold spaces, control characters or any of ~ ^ : ? * [ \\";
  if (ref.includes("..") || ref.includes("@{") || ref.includes("//")) return "A branch name cannot contain .. or @{ or //";
  if (ref.startsWith("/") || ref.endsWith("/")) return "A branch name cannot start or end with /";
  if (ref.startsWith("-")) return "A branch name cannot start with -";
  if (ref.endsWith(".")) return "A branch name cannot end with .";
  if (ref.split("/").some((part) => part.endsWith(".lock"))) return "No part of a branch name can end with .lock";
  return null;
}
