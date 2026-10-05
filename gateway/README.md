# Gateway

NGINX in front of every QA Vision service. Configuration only — no code.
Design: `docs/superpowers/specs/2026-09-28-api-gateway-design.md`.

## Routes

| Path | Service |
|---|---|
| `/api/v1/organizations/{id}/projects…` | project-service |
| `/api/v1/projects/{id}/api-keys…`, `…/runs…`, `…/analytics…`, `…/masking-patterns…`, `…/export`, `…/notification-channels…` | ingestion-service |
| `/api/v1/runs…`, `/api/v1/collect…` | ingestion-service |
| `/api/v1/projects…` | project-service |
| `/api/v1/organizations…`, `/api/v1/invitations…` | organization-service |
| `/api/v1/auth…`, `/api/v1/users…`, `/api/v1/sso…` | auth-service |
| `/health` | the gateway itself |
| `/health/auth`, `/health/organizations`, `/health/projects`, `/health/ingestion` | that service's `/health` |
| anything else | `404 {"detail":"Not Found"}` |

The first row is a regex location: NGINX checks regex locations before prefix ones, which is
what takes `/organizations/{id}/projects` away from organization-service.

## Limits

- Per client IP: 20 requests/s (burst 40) on every `/api/v1` route; additionally 5 requests/s
  (burst 10) on `login`, `mfa/verify`, `register`, `forgot-password`, `reset-password`,
  `change-password`, `resend-verification`.
  Over the limit: `429 {"detail":"Too Many Requests"}` with `Retry-After: 1`. Health routes are
  never limited.
- `/api/v1/collect` has its own limit instead: 10 requests/s per IP (burst 20).
- Request bodies up to 10 MB; upstream connect timeout 3 s, read timeout 30 s.
- NGINX's own errors (404, 413, 429, 502, 504) are JSON; the services' errors pass through.

## TLS

HTTPS on host port `${GATEWAY_HTTPS_PORT:-8443}`; HTTP on `${GATEWAY_HTTP_PORT:-8080}` redirects
to it. On first start the entrypoint generates a self-signed certificate for `localhost` into the
`qav_gateway_certs` volume. Use `curl -k`, or trust it once:
`docker compose cp gateway:/etc/nginx/certs/tls.crt ./qav-localhost.crt`.
To use your own, put `tls.crt` and `tls.key` in that volume before starting.

## Requests and logs

Every response carries `X-Request-ID` (yours if you sent one); the same id is forwarded to the
service. `X-Forwarded-For` is replaced with the connecting address, never appended to, so a client
cannot choose its own rate-limit bucket. `docker compose logs gateway` shows one JSON line per
request.

## Adding a service

1. In `nginx.conf.template`, add a `location` for its path prefix with
   `limit_req zone=api burst=40 nodelay;`, `set $upstream http://<service>:8000;` and
   `proxy_pass $upstream;` — plus a `= /health/<name>` location. Keep the upstream in a variable:
   that is what lets the gateway find a recreated container without a restart.
2. In the root `docker-compose.yml`, add the service, its `-migrate` job, its database to
   `scripts/postgres-init.sh`, and a `depends_on` entry under `gateway`.
3. Add a routing check and a `/health/<name>` check to `scripts/smoke_gateway.sh`.

## Checking a change

```bash
docker build -t qa-vision/gateway:local gateway && docker run --rm qa-vision/gateway:local nginx -t
export SECRET_KEY=dev        # every docker compose command needs it, not just `up`
docker compose up -d --build --wait gateway
bash scripts/smoke_gateway.sh
```
