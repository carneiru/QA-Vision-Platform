#!/usr/bin/env bash
# End-to-end checks through the gateway, one per routing rule and gateway feature.
# Run from anywhere after:  SECRET_KEY=... docker compose up -d --build --wait gateway
set -uo pipefail
cd "$(dirname "$0")/.."

# docker-compose.yml interpolates ${SECRET_KEY:?...} for EVERY compose command, including the
# `exec` below, so without it nothing here can work -- say so instead of failing obscurely.
if [ -z "${SECRET_KEY:-}" ]; then
  echo "FAIL  SECRET_KEY is not set: export the same value the stack was started with"
  exit 1
fi

HTTPS_PORT="${GATEWAY_HTTPS_PORT:-8443}"
HTTP_PORT="${GATEWAY_HTTP_PORT:-8080}"
BASE="https://localhost:${HTTPS_PORT}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
failures=0

pass() { printf 'ok    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

# check NAME EXPECTED_STATUS METHOD URL [curl args...]; body -> $TMP/body, headers -> $TMP/headers
check() {
  local name="$1" expected="$2" method="$3" url="$4"
  shift 4
  local status
  status="$(curl -ks -o "$TMP/body" -D "$TMP/headers" -w '%{http_code}' -X "$method" "$@" "$url")"
  if [ "$status" = "$expected" ]; then
    pass "$name ($status)"
  else
    fail "$name: expected $expected, got $status: $(head -c 300 "$TMP/body" 2>/dev/null)"
  fi
}

# body_has NAME TEXT -- the last response body contains TEXT
body_has() {
  if grep -qF -- "$2" "$TMP/body" 2>/dev/null; then
    pass "$1"
  else
    fail "$1: body was $(head -c 300 "$TMP/body" 2>/dev/null)"
  fi
}

# A valid access token for a user id that is a member of nothing, signed with the stack's key
TOKEN="$(docker compose exec -T auth-service python -c '
import datetime, os, jwt
exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
print(jwt.encode({"sub": "999999", "exp": exp}, os.environ["SECRET_KEY"], algorithm="HS256"))
' 2>"$TMP/mint_err" | tr -d '\r\n')"
if [ -z "$TOKEN" ]; then
  echo "FAIL  could not mint a token inside auth-service: $(head -c 300 "$TMP/mint_err")"
  exit 1
fi
AUTH=(-H "Authorization: Bearer ${TOKEN}")

# ---- gateway and health ----
check "gateway /health" 200 GET "$BASE/health"
body_has "gateway /health body" '{"status":"healthy"}'
for svc in auth organizations projects; do
  check "/health/$svc reaches the service" 200 GET "$BASE/health/$svc"
done

# ---- one real call per routing rule ----
check "/api/v1/users/me with a bad token -> auth-service" 401 GET "$BASE/api/v1/users/me" \
  -H "Authorization: Bearer not-a-token"
check "/api/v1/organizations/1/members/me for a non-member -> organization-service" 404 GET \
  "$BASE/api/v1/organizations/1/members/me" "${AUTH[@]}"
check "/api/v1/organizations/1/projects -> project-service (overlap route)" 404 GET \
  "$BASE/api/v1/organizations/1/projects" "${AUTH[@]}"
body_has "... answered only after organization-service said 404 (shared network works)" \
  '"Organization not found"'
check "/api/v1/projects/1 -> project-service" 404 GET "$BASE/api/v1/projects/1" "${AUTH[@]}"
body_has "... answered by project-service" '"Project not found"'

# ---- gateway behaviour ----
check "unknown path" 404 GET "$BASE/no/such/path"
body_has "unknown path answers JSON" '{"detail":"Not Found"}'
if grep -qi '^x-request-id: ' "$TMP/headers"; then pass "X-Request-ID on responses"; else fail "no X-Request-ID header"; fi

check "client X-Request-ID is echoed" 200 GET "$BASE/health" -H "X-Request-ID: smoke-123"
if grep -qi '^x-request-id: smoke-123' "$TMP/headers"; then pass "X-Request-ID echo value"; else fail "X-Request-ID not echoed"; fi

# A service's own trailing-slash redirect must send the client back through the gateway, on
# HTTPS and the published port -- not to http://localhost/ (host port 80, no gateway there)
check "service redirect (GET /api/v1/users -> /api/v1/users/)" 307 GET "$BASE/api/v1/users" "${AUTH[@]}"
if grep -qi "^location: https://localhost:${HTTPS_PORT}/api/v1/users/" "$TMP/headers"; then
  pass "service redirect stays on https://localhost:${HTTPS_PORT}"
else
  fail "service redirect points elsewhere: $(grep -i '^location' "$TMP/headers" 2>/dev/null)"
fi

redirect_status="$(curl -s -o /dev/null -D "$TMP/redirect" -w '%{http_code}' "http://localhost:${HTTP_PORT}/health")"
if [ "$redirect_status" = 301 ] && grep -qi "^location: https://localhost:${HTTPS_PORT}/health" "$TMP/redirect"; then
  pass "HTTP redirects to HTTPS on port ${HTTPS_PORT}"
else
  fail "HTTP redirect: got $redirect_status, $(grep -i '^location' "$TMP/redirect" 2>/dev/null)"
fi

# ---- rate limiting last: it leaves this client's auth bucket drained for a few seconds ----
# 30 requests in ONE curl, sent concurrently. A loop of separate curl processes can be slower than
# the 5 r/s limit itself (about 550 ms per process on Windows), and would then never see a 429.
# Each response (status line, headers, body: -i) goes to its own file, so a rejected one can be
# inspected afterwards -- a follow-up request would arrive after the bucket had refilled.
LOGIN="$BASE/api/v1/auth/login"
args=()
for i in $(seq 1 30); do args+=(-o "$TMP/rl_$i" "$LOGIN"); done
curl -ks -i --parallel --parallel-max 30 -X POST "${args[@]}"
rejected=()
for i in $(seq 1 30); do
  if head -1 "$TMP/rl_$i" 2>/dev/null | grep -q ' 429'; then rejected+=("$TMP/rl_$i"); fi
done
if [ "${#rejected[@]}" -gt 0 ]; then
  pass "rate limit on /api/v1/auth/login (${#rejected[@]} of 30 concurrent requests got 429)"
  cp "${rejected[0]}" "$TMP/body"
  body_has "429 answers JSON" '{"detail":"Too Many Requests"}'
  if grep -qi '^retry-after: 1' "${rejected[0]}"; then pass "429 carries Retry-After: 1"; else fail "429 without Retry-After"; fi
else
  fail "rate limit on /api/v1/auth/login: 30 concurrent requests, none got 429"
fi

if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed"
  exit 1
fi
echo "all gateway checks passed"
