/** Where a signed-out visitor was going, kept in `?next=` so sign-in can return there. */

/**
 * The `next` value when it is a same-origin relative path, else null: it must start with a single "/",
 * and carry no backslash, whitespace or control character (browsers strip tabs and newlines, so
 * "/\t/evil.example" would otherwise become "//evil.example"), so it can never leave the site.
 */
export function safeNext(raw: string | null | undefined): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return null;
  // eslint-disable-next-line no-control-regex
  if (/[\\\s\u0000-\u001f\u007f]/.test(raw)) return null;
  // Back to the login page would loop
  if (raw === "/login" || raw.startsWith("/login?") || raw.startsWith("/login/") || raw.startsWith("/login#")) return null;
  return raw;
}

interface Where {
  pathname: string;
  search: string;
  hash: string;
}

/** The login URL for a visitor who was at `from`; `reason: "expired"` makes the page say the session ended. */
export function loginPath(from: Where, reason?: "expired"): string {
  const params = new URLSearchParams();
  const target = from.pathname + from.search + from.hash;
  if (target !== "/") params.set("next", target);
  if (reason) params.set("reason", reason);
  const query = params.toString();
  return query ? `/login?${query}` : "/login";
}
