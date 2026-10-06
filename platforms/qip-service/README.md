# UNWIRED PROTOTYPE

This directory is prototype code: it is not in docker-compose.yml, not in CI,
not routed by the gateway and has no migrations. Nothing here runs in the
platform today. See ARCHITECTURE_EVOLUTION.md and IMPLEMENTATION_PLAN.md
(section 5) before building on it: revive deliberately when its capability's
adoption trigger fires, or archive it.

## Before reviving: authentication

Its JWT code predates two platform rules, so do not wire it up as it is:

- Every service must refuse a token that carries a `purpose` or `token_type` claim as a user
  session. Those are MFA challenge and CI service tokens (ADR-024). Copy `is_access_token` from any
  wired service's `utils/tokens.py` into `security/jwt.py`, `middleware/auth.py` and
  `middleware/permissions.py`, which today accept any token signed with `SECRET_KEY`.
- `config.py` defaults `SECRET_KEY` to `"your-secret-key-here"`. A wired service must refuse to
  start without a real key, as the others do through `qav_shared.config`.
