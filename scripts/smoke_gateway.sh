#!/usr/bin/env bash
# End-to-end checks through the gateway, one per routing rule and gateway feature.
# Run from anywhere after:  SECRET_KEY=... INTERNAL_API_PASSWORD=... docker compose up -d --build --wait gateway
set -uo pipefail
cd "$(dirname "$0")/.."

# docker-compose.yml interpolates ${SECRET_KEY:?...} for EVERY compose command, including the
# `exec` below, so without it nothing here can work -- say so instead of failing obscurely.
for var in SECRET_KEY INTERNAL_API_PASSWORD; do
  if [ -z "${!var:-}" ]; then
    echo "FAIL  $var is not set: export the same value the stack was started with"
    exit 1
  fi
done

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

# body_lacks NAME TEXT -- the last response body does not contain TEXT
body_lacks() {
  if grep -qF -- "$2" "$TMP/body" 2>/dev/null; then
    fail "$1: the body contains it"
  else
    pass "$1"
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
for svc in auth organizations projects ingestion test-management; do
  check "/health/$svc reaches the service" 200 GET "$BASE/health/$svc"
done

# ---- one real call per routing rule ----
check "/api/v1/users/me with a bad token -> auth-service" 401 GET "$BASE/api/v1/users/me" \
  -H "Authorization: Bearer not-a-token"
# The stack has no Microsoft configuration: 503 proves the request reached auth-service
check "/api/v1/sso/microsoft -> auth-service (not configured)" 503 POST "$BASE/api/v1/sso/microsoft" \
  -H "Content-Type: application/json" -d '{"credential":"not-a-token"}'
check "/api/v1/organizations/999999/members/me for a non-member -> organization-service" 404 GET \
  "$BASE/api/v1/organizations/999999/members/me" "${AUTH[@]}"
check "/api/v1/organizations/999999/projects -> project-service (overlap route)" 404 GET \
  "$BASE/api/v1/organizations/999999/projects" "${AUTH[@]}"
body_has "... answered only after organization-service said 404 (shared network works)" \
  '"Organization not found"'
check "/api/v1/projects/999999 -> project-service" 404 GET "$BASE/api/v1/projects/999999" "${AUTH[@]}"
body_has "... answered by project-service" '"Project not found"'

# ---- ingestion: key -> upload -> replay -> read -> revoke, through the gateway ----
# The smoke user creates its own organization and project, so it may manage an API key.
# Unique names: the script must also pass when run again on the same volume.
SUFFIX="$(date +%s)-$$"
check "create an organization" 201 POST "$BASE/api/v1/organizations" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Smoke $SUFFIX\",\"slug\":\"smoke-$SUFFIX\",\"plan_tier\":\"free\"}"
ORG_ID="$(grep -o '"id":[0-9]*' "$TMP/body" | head -1 | cut -d: -f2)"
check "create a project" 201 POST "$BASE/api/v1/organizations/$ORG_ID/projects" "${AUTH[@]}" \
  -H "Content-Type: application/json" -d "{\"name\":\"Smoke $SUFFIX\"}"
PROJECT_ID="$(grep -o '"id":[0-9]*' "$TMP/body" | head -1 | cut -d: -f2)"
check "create an API key -> ingestion-service (overlap route)" 201 POST \
  "$BASE/api/v1/projects/$PROJECT_ID/api-keys" "${AUTH[@]}" -H "Content-Type: application/json" -d '{"name":"smoke"}'
API_KEY="$(sed -n 's/.*"key":"\(qav_[^"]*\)".*/\1/p' "$TMP/body")"
KEY_ID="$(grep -o '"id":[0-9]*' "$TMP/body" | head -1 | cut -d: -f2)"
# ---- test-management-service: a case through the gateway (ADR-022) ----
check "create a test case -> test-management-service (overlap route)" 201 POST   "$BASE/api/v1/projects/$PROJECT_ID/cases" "${AUTH[@]}" -H "Content-Type: application/json"   -d '{"title":"Smoke case","labels":["smoke"]}'
body_has "... numbered in the project" '"key":"TC-1"'
check "list case labels -> test-management-service" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/case-labels" "${AUTH[@]}"
check "list suites -> test-management-service" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/suites" "${AUTH[@]}"
IMPORT_BODY='{"files":[{"path":"tests/features/smoke.feature","content":"Feature: Smoke\n  Scenario: imported\n    Given the gateway\n"}]}'
check "import a .feature -> test-management-service" 200 POST "$BASE/api/v1/projects/$PROJECT_ID/cases/import" \
  "${AUTH[@]}" -H "Content-Type: application/json" -d "$IMPORT_BODY"
body_has "... one case created" '"created":1'
check "case folders -> test-management-service" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/case-folders" "${AUTH[@]}"
body_has "... the imported folder is listed" '"path":"tests/features"'
check "case features -> test-management-service" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/case-features" "${AUTH[@]}"
check "search cases by test keys -> test-management-service" 200 POST "$BASE/api/v1/projects/$PROJECT_ID/cases/search" \
  "${AUTH[@]}" -H "Content-Type: application/json" -d '{"test_keys":[],"keys_mode":"exclude"}'
check "latest-keys -> ingestion-service" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/analytics/latest-keys?status=any" "${AUTH[@]}"
check "run-strip -> ingestion-service" 200 POST "$BASE/api/v1/projects/$PROJECT_ID/analytics/run-strip" \
  "${AUTH[@]}" -H "Content-Type: application/json" -d "{\"test_keys\":[\"$(printf 'a%.0s' $(seq 64))\"]}"
body_has "... returns statuses" '"statuses"'
# A body over the gateway's general 10 MB cap must still reach the service on the import path:
# the service answers 413 naming its own setting, not NGINX's bare 413 page.
# 55 files x 200000 bytes, built with plain shell so no Python is needed.
XS="$(head -c 200000 /dev/zero | tr '\0' x)"
{
  printf '{"files":['
  for i in $(seq 1 55); do
    [ "$i" -gt 1 ] && printf ','
    printf '{"path":"f%s.feature","content":"%s"}' "$i" "$XS"
  done
  printf ']}'
} > "$TMP/big.json"
check "an 11 MB import reaches the service" 413 POST "$BASE/api/v1/projects/$PROJECT_ID/cases/import" \
  "${AUTH[@]}" -H "Content-Type: application/json" --data-binary "@$TMP/big.json"
body_has "... and the service answered it" 'IMPORT_MAX_TOTAL_BYTES'
# ---- CI import: trade the API key for a short-lived token, import with it (ADR-024) ----
check "trade the API key for an import token -> ingestion-service" 200 POST "$BASE/api/v1/collect/token" \
  -H "Authorization: Bearer $API_KEY"
SERVICE_TOKEN="$(sed -n 's/.*"token":"\([^"]*\)".*/\1/p' "$TMP/body")"
CI_BODY='{"files":[{"path":"tests/features/ci.feature","content":"Feature: CI\n  Scenario: from ci\n    Given a token\n"}]}'
check "import a .feature with the CI token -> test-management-service" 200 POST \
  "$BASE/api/v1/projects/$PROJECT_ID/cases/import" -H "Authorization: Bearer $SERVICE_TOKEN" \
  -H "Content-Type: application/json" -d "$CI_BODY"
body_has "... one case created by CI" '"created":1'
check "the CI token opens no other route" 401 GET "$BASE/api/v1/projects/$PROJECT_ID/cases" \
  -H "Authorization: Bearer $SERVICE_TOKEN"
check "list API keys -> ingestion-service" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/api-keys" "${AUTH[@]}"
body_has "... listing hides the key" "\"key_prefix\""
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUN_BODY="{\"run\":{\"ci_provider\":\"local\",\"branch\":\"smoke\",\"started_at\":\"$NOW\",\"finished_at\":\"$NOW\"},\"results\":[{\"name\":\"passes\",\"status\":\"passed\"},{\"name\":\"fails\",\"status\":\"failed\",\"message\":\"boom\"}]}"
check "upload a run -> /api/v1/collect" 201 POST "$BASE/api/v1/collect/runs" \
  -H "Authorization: Bearer $API_KEY" -H "Idempotency-Key: smoke-$SUFFIX" -H "Content-Type: application/json" \
  -d "$RUN_BODY"
body_has "... counts computed by the server" '"failed":1'
RUN_ID="$(grep -o '"id":[0-9]*' "$TMP/body" | head -1 | cut -d: -f2)"
check "replay with the same Idempotency-Key" 200 POST "$BASE/api/v1/collect/runs" \
  -H "Authorization: Bearer $API_KEY" -H "Idempotency-Key: smoke-$SUFFIX" -H "Content-Type: application/json" \
  -d "$RUN_BODY"
body_has "... returns the same run" "\"id\":$RUN_ID"
check "list runs -> ingestion-service (overlap route)" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/runs" "${AUTH[@]}"
body_has "... includes the run" "\"id\":$RUN_ID"
check "read the run -> /api/v1/runs" 200 GET "$BASE/api/v1/runs/$RUN_ID?status=failed" "${AUTH[@]}"
body_has "... with the failed result" '"name":"fails"'

# ---- the collector, end to end: JUnit file -> qav-collector -> gateway -> ingestion ----
# Runs from collector/src, so nothing is installed; the CI collector job covers installing it.
PY=""
for candidate in python3 python; do
  if "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  fail "collector: no Python 3.9+ found (tried python3, python)"
else
  # The gateway's self-signed certificate, so the collector verifies TLS instead of skipping it.
  # The path goes through sh -c: Git Bash on Windows rewrites a bare /etc/... argument to C:/...
  docker compose exec -T gateway sh -c 'cat /etc/nginx/certs/tls.crt' > "$TMP/gateway.crt"
  [ -s "$TMP/gateway.crt" ] || fail "collector: could not read the gateway's certificate"
  cat > "$TMP/junit.xml" <<'XML'
<testsuites>
  <testsuite name="smoke">
    <testcase classname="smoke" name="passes" time="0.1"/>
    <testcase classname="smoke" name="fails" time="0.2"><failure message="boom">boom</failure></testcase>
    <testcase classname="smoke" name="skips"><skipped/></testcase>
  </testsuite>
</testsuites>
XML
  if (cd collector/src && QAV_URL="$BASE" QAV_API_KEY="$API_KEY" "$PY" -m qav_collector upload \
        "$TMP/junit.xml" --ca-file "$TMP/gateway.crt" --branch smoke-collector --fail-on-error) \
        2>"$TMP/collector_err"; then
    pass "collector uploads a JUnit file through the gateway"
  else
    fail "collector upload: $(tail -c 400 "$TMP/collector_err")"
  fi
  if grep -qF -- "$API_KEY" "$TMP/collector_err"; then
    fail "collector output contains the API key"
  else
    pass "collector output never shows the API key"
  fi
  COLLECTOR_RUN_ID="$(sed -n 's/.*uploaded run \([0-9][0-9]*\).*/\1/p' "$TMP/collector_err" | head -1)"
  check "read the collector's run" 200 GET "$BASE/api/v1/runs/${COLLECTOR_RUN_ID:-0}" "${AUTH[@]}"
  body_has "... with the collector's counts" '"total":3,"passed":1,"failed":1,"skipped":1,"errored":0'
fi

# ---- masking: secrets in test output never reach the database ----
FAKE_TOKEN="ghp_"'SmokeSmokeSmokeSmokeSmokeSmokeSmoke0'  # token-shaped, not a real token
MASK_BODY="{\"run\":{\"ci_provider\":\"local\",\"branch\":\"smoke-mask\",\"started_at\":\"$NOW\",\"finished_at\":\"$NOW\"},\"results\":[{\"name\":\"leaks\",\"status\":\"failed\",\"message\":\"login as ann@acme.test\",\"details\":\"GITHUB_TOKEN=$FAKE_TOKEN\"}]}"
check "upload a run whose output contains a token" 201 POST "$BASE/api/v1/collect/runs" \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" -d "$MASK_BODY"
MASK_RUN_ID="$(grep -o '"id":[0-9]*' "$TMP/body" | head -1 | cut -d: -f2)"
check "read the masked run" 200 GET "$BASE/api/v1/runs/${MASK_RUN_ID:-0}" "${AUTH[@]}"
body_has "... the token is masked" '[REDACTED:github_token]'
body_has "... the email is masked" '[REDACTED:email]'
body_has "... and the result is flagged" '"redacted":true'
body_lacks "... the token itself is not stored" "$FAKE_TOKEN"


# ---- analytics, through the gateway's overlap route ----
check "analytics trends -> ingestion-service (overlap route)" 200 GET \
  "$BASE/api/v1/projects/$PROJECT_ID/analytics/trends?days=2" "${AUTH[@]}"
if grep -qE '"runs":[1-9]' "$TMP/body"; then
  pass "... the runs uploaded above are counted"
else
  fail "... no runs counted: $(head -c 300 "$TMP/body")"
fi
check "analytics tests" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/analytics/tests?search=fails" "${AUTH[@]}"
body_has "... lists the failing test" '"name":"fails"'
FAILS_KEY="$(sed -n 's/.*"test_key":"\([0-9a-f]\{64\}\)".*/\1/p' "$TMP/body" | head -1)"
check "analytics history of that test" 200 GET \
  "$BASE/api/v1/projects/$PROJECT_ID/analytics/tests/${FAILS_KEY:-0}/history" "${AUTH[@]}"
body_has "... with its executions" '"executions":[{'
check "analytics flaky" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/analytics/flaky" "${AUTH[@]}"


check "revoke the key" 204 DELETE "$BASE/api/v1/projects/$PROJECT_ID/api-keys/$KEY_ID" "${AUTH[@]}"
check "a revoked key is rejected" 401 POST "$BASE/api/v1/collect/runs" \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" -d "$RUN_BODY"
# ---- organization membership: register -> invite -> accept -> role, through the gateway ----
# The minted smoke token (sub 999999) is no real user, so the member flow needs one: register,
# verify (token read from the database, as a person would read it from the email), log in.
INVITEE="smoke-invitee-$SUFFIX@example.com"
check "register the invitee" 202 POST "$BASE/api/v1/auth/register" \
  -H "Content-Type: application/json" -d "{\"email\":\"$INVITEE\",\"password\":\"Smoke-pw-123456\"}"
VERIFY_TOKEN="$(docker compose exec -T postgres psql -U postgres -d auth_db -tAc \
  "SELECT token FROM pending_registrations WHERE email='$INVITEE' ORDER BY id DESC LIMIT 1" | tr -d ' \r\n')"
check "verify the invitee's email" 200 GET "$BASE/api/v1/auth/verify-email?token=$VERIFY_TOKEN"
check "invitee login" 200 POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/json" -d "{\"email\":\"$INVITEE\",\"password\":\"Smoke-pw-123456\"}"
INVITEE_TOKEN="$(grep -o '"access_token":"[^"]*"' "$TMP/body" | head -1 | cut -d'"' -f4)"
INVITEE_AUTH=(-H "Authorization: Bearer ${INVITEE_TOKEN}")

# Adding a nonexistent user answers a clean 422: organization-service asked auth-service's
# internal API (the superuser AUTH_SERVICE_TOKEN is gone)
check "direct member add of a nonexistent user" 422 POST "$BASE/api/v1/organizations/$ORG_ID/members" \
  "${AUTH[@]}" -H "Content-Type: application/json" -d '{"user_id":987654321,"role":"member"}'
body_has "... names the reason" 'user not found'

check "create an invitation" 201 POST "$BASE/api/v1/organizations/$ORG_ID/invitations" \
  "${AUTH[@]}" -H "Content-Type: application/json" -d "{\"email\":\"$INVITEE\",\"role\":\"member\"}"
INVITE_TOKEN="$(grep -o '"token":"[^"]*"' "$TMP/body" | head -1 | cut -d'"' -f4)"
check "the invitation list answers" 200 GET "$BASE/api/v1/organizations/$ORG_ID/invitations" "${AUTH[@]}"
body_lacks "the list never shows the raw token" "${INVITE_TOKEN:-no-token-found}"
check "the invitee previews the invitation" 200 GET "$BASE/api/v1/invitations/${INVITE_TOKEN:-none}" "${INVITEE_AUTH[@]}"
body_has "... which names the organization" '"organization_name":"Smoke '
check "accept the invitation" 201 POST "$BASE/api/v1/invitations/${INVITE_TOKEN:-none}/accept" "${INVITEE_AUTH[@]}"
check "the invitee's role in the organization" 200 GET \
  "$BASE/api/v1/organizations/$ORG_ID/members/me" "${INVITEE_AUTH[@]}"
body_has "... is member" '"role":"member"'
check "an accepted token cannot be used again" 404 POST \
  "$BASE/api/v1/invitations/${INVITE_TOKEN:-none}/accept" "${INVITEE_AUTH[@]}"
check "the member list carries emails from auth-service" 200 GET \
  "$BASE/api/v1/organizations/$ORG_ID/members" "${INVITEE_AUTH[@]}"
body_has "... the invitee's email is on their row" "$INVITEE"

# The catch-all now serves the dashboard SPA, so these paths answer its HTML,
# never a proxied service: the security intent is "not reachable", not "404".
check "/metrics is not proxied (SPA fallback)" 200 GET "$BASE/metrics"
body_has "/metrics serves the SPA, not metrics" '<div id="root">'
body_lacks "/metrics leaks no Prometheus text" '# HELP'
check "/internal is not proxied (SPA fallback)" 200 GET "$BASE/internal/v1/projects/retention"
body_has "/internal serves the SPA" '<div id="root">'

# ---- retention: the job runs, and really reaches project-service inside the stack ----
if docker compose ps --status running --services 2>/dev/null | grep -qx ingestion-retention; then
  pass "ingestion-retention is running"
else
  fail "ingestion-retention is not running"
fi
if docker compose ps --status running --services 2>/dev/null | grep -qx analytics-rollup; then
  pass "analytics-rollup is running"
else
  fail "analytics-rollup is not running"
fi
if docker compose run --rm -T ingestion-retention python -m src.ingestion.jobs.retention --dry-run \
     >"$TMP/retention_out" 2>"$TMP/retention_err"; then
  if grep -q '"event": "retention"' "$TMP/retention_out"; then
    pass "retention job dry run inside the stack"
  else
    fail "retention job dry run printed no summary: $(tail -c 300 "$TMP/retention_out")"
  fi
else
  fail "retention job dry run: $(tail -c 400 "$TMP/retention_err")"
fi
if grep -qF -- "$INTERNAL_API_PASSWORD" "$TMP/retention_out" "$TMP/retention_err"; then
  fail "retention job output contains the internal password"
else
  pass "retention job output never shows the internal password"
fi

# Unknown API paths keep the old JSON 404 contract: scripts and JSON clients
# must never receive the SPA's HTML with a 200.
check "unknown API path stays a JSON 404" 404 GET "$BASE/api/v1/no/such/path"
body_has "unknown API path answers JSON" '{"detail":"Not Found"}'

# ---- dashboard SPA ----
check "dashboard index" 200 GET "$BASE/"
body_has "dashboard index is the SPA" '<div id="root">'
check "SPA deep link falls back to index" 200 GET "$BASE/projects/1/trends"
body_has "deep link serves the SPA" '<div id="root">'

# The index references hashed assets; one must load and carry the immutable cache policy.
ASSET="$(grep -oE '/assets/[A-Za-z0-9._-]+\.js' "$TMP/body" | head -1)"
if [ -n "$ASSET" ]; then
  check "hashed SPA asset loads" 200 GET "$BASE$ASSET"
  if grep -qiE '^cache-control:.*immutable' "$TMP/headers"; then
    pass "SPA asset is immutable-cached"
  else
    fail "SPA asset missing immutable Cache-Control: $(grep -i '^cache-control' "$TMP/headers" | head -1)"
  fi
else
  fail "no hashed asset path found in the SPA index"
fi

# ---- gateway behaviour ----
check "unknown path serves the SPA" 200 GET "$BASE/no/such/path"
body_has "unknown path answers the SPA" '<div id="root">'
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
