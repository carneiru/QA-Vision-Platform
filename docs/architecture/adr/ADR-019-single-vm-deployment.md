# ADR-019: First production deployment is one VM: Compose + a Caddy TLS edge

Status: Accepted (2026-10-05) · Evidence: deploy/, verified locally with an isolated prod-config stack

## Context
CI on hosted runners needs a stable public address; a laptop tunnel changes address on every
restart, depends on the laptop being on, and exposes a corporate machine. The blueprint's
Kubernetes trigger is the first *multi-node* deployment, which this is not.

## Decision
Run the existing Compose stack on one Linux VM, plus one service: Caddy as the TLS edge
(Let's Encrypt issuance and renewal), the only published service. The NGINX gateway stays
the application edge (routing, rate limits, JSON errors, request ids) and is no longer
published. Behind the edge, per-IP rate limits would see one address for everyone, so the
gateway trusts `X-Forwarded-For` (nginx real_ip, recursive) from Caddy's fixed address only
— not the subnet, which includes the Docker host's bridge address; dynamic addresses come
from the upper half of the subnet so nothing can take Caddy's. `deploy/init-env.sh` writes
strong secrets; `deploy/backup.sh` dumps all databases daily with 14-day retention.

## Consequences
Verified on an isolated stack: chain validated by OpenSSL, HSTS sent, a spoofed
`X-Forwarded-For` ignored, one client exhausting the login limit (19/30 → 429) while a second
client is unaffected, verification links on the public domain, backup restored into an
empty PostgreSQL with all four databases. Single point of failure and no horizontal scale —
acceptable until a trigger fires; moving to Kubernetes later changes the edge, not the app.
