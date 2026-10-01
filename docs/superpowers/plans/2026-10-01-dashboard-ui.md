# Dashboard UI (Analytics MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A React SPA served behind the existing NGINX gateway that logs in with the platform's JWT auth and renders the four analytics views (trends, tests, history, flaky) for a chosen project.

**Architecture:** New top-level `dashboard/` (Vite + React + TypeScript) built to static files and served by its own nginx container; the gateway's final `location /` proxies to it, so the SPA and the API share one origin. One new backend endpoint (`GET /api/v1/organizations`) lets the picker enumerate the user's organizations.

**Tech Stack:** React 18, React Router 6, TanStack Query 5, Recharts 2, Vite 5, Vitest + React Testing Library + MSW 2, nginx:alpine. Backend task uses the existing FastAPI/SQLAlchemy/pytest stack of organization-service.

**Spec:** `docs/superpowers/specs/2026-10-01-dashboard-ui-design.md`

## Global Constraints

- Branch: `feat/dashboard-ui` (stacked on `feat/analytics-api`; rebase onto master after PR #14 merges).
- Access token lives in memory only; refresh token in `sessionStorage` under key `qav.refresh`.
- All API calls are same-origin relative paths (`/api/v1/...`) — never an absolute host; no CORS changes anywhere.
- Auth endpoints (exact): `POST /api/v1/auth/login` body `{"email","password"}`; `POST /api/v1/auth/refresh-token` body `{"refresh_token"}`; `POST /api/v1/auth/logout` body `{"refresh_token"}`. All return/accept JSON; Token response is `{"access_token","refresh_token","token_type"}`.
- Charts: NEVER a dual-axis chart. Status colors fixed: passed `#0ca30c`, failed `#d03b3b`, errored `#ec835a`, skipped `#898781`; status is never conveyed by color alone (text label or legend always present).
- `pass_rate` from the API is a 0..1 fraction or null; render as percent with one decimal, and render null as "—", never `NaN`.
- `test_key` values may contain `/`, `::`, spaces — always `encodeURIComponent` them in URLs (fetch paths and router links).
- Node 22 / `npm ci` in CI; Python side unchanged (3.11, pytest).
- Commit after every task with the exact message given; every commit message ends with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## Review Focus

Failure modes the spec implies; each has its pinning test in the named task:

1. Two requests hit 401 at once → exactly one refresh call, both retried; a second 401 after refresh logs out instead of looping. (Task 4)
2. The gateway answers with a non-JSON body (502/429 HTML or truncated) → user sees a readable banner, not an unhandled parse crash. (Task 4)
3. A user who belongs to zero organizations → picker renders an empty state, not a crash or infinite spinner. (Task 6)
4. A `test_key` like `tests/test_login.py::TestLogin::test_ok` → history fetch and router link both encode it; the API receives the exact key. (Task 7 client test; Task 10 link test)
5. Trend days with `pass_rate: null` (only skipped tests that day) → chart and table render "—", no `NaN`, chart does not draw a bogus 0 point. (Task 9)

---

### Task 1: organization-service — GET /api/v1/organizations (list my organizations)

**Files:**
- Modify: `platforms/organization-service/src/organization/schemas/organization.py`
- Modify: `platforms/organization-service/src/organization/service/organization_service.py`
- Modify: `platforms/organization-service/src/organization/api/v1/endpoints/organizations.py`
- Test: `platforms/organization-service/tests/integration/test_organizations_list.py`

**Interfaces:**
- Consumes: existing `get_db`, `get_current_user_id` deps; `Organization`, `OrganizationMember` models.
- Produces: `GET /api/v1/organizations` → `200 [{id, name, slug, plan_tier, created_at, updated_at, role}]`, ordered by name. Only organizations where the caller is an **active** member and the org is not soft-deleted. 401 without a token. The gateway's existing `location /api/v1/organizations` prefix already routes it — no gateway change.

- [ ] **Step 1: Write the failing tests**

Create `platforms/organization-service/tests/integration/test_organizations_list.py` (same `_token`/`_auth` helpers as `test_organizations_endpoints.py`):

```python
import jwt
from datetime import datetime, timedelta, timezone
from src.organization.core.config import settings
from src.organization.models.member import OrganizationMember


def _token(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _auth(user_id: int) -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


def _create(client, user_id: int, name: str, slug: str) -> int:
    r = client.post(
        "/api/v1/organizations",
        json={"name": name, "slug": slug, "plan_tier": "free"},
        headers=_auth(user_id),
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_list_requires_auth(client):
    assert client.get("/api/v1/organizations").status_code == 401


def test_list_returns_only_my_orgs_with_role(client):
    mine = _create(client, 7, "Mine", "mine")
    _create(client, 8, "Theirs", "theirs")

    r = client.get("/api/v1/organizations", headers=_auth(7))
    assert r.status_code == 200
    body = r.json()
    assert [o["id"] for o in body] == [mine]
    assert body[0]["role"] == "owner"
    assert body[0]["name"] == "Mine"


def test_list_empty_for_user_with_no_orgs(client):
    r = client.get("/api/v1/organizations", headers=_auth(99))
    assert r.status_code == 200
    assert r.json() == []


def test_list_excludes_soft_deleted(client):
    org_id = _create(client, 7, "Gone", "gone")
    assert client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(7)).status_code == 204
    r = client.get("/api/v1/organizations", headers=_auth(7))
    assert [o["id"] for o in r.json()] == []


def test_list_excludes_inactive_membership(client, db):
    org_id = _create(client, 7, "Acme", "acme")
    member = (
        db.query(OrganizationMember)
        .filter_by(organization_id=org_id, user_id=7)
        .one()
    )
    member.status = "suspended"
    db.commit()
    r = client.get("/api/v1/organizations", headers=_auth(7))
    assert r.json() == []


def test_list_ordered_by_name(client):
    _create(client, 7, "Zeta", "zeta")
    _create(client, 7, "Alpha", "alpha")
    r = client.get("/api/v1/organizations", headers=_auth(7))
    assert [o["name"] for o in r.json()] == ["Alpha", "Zeta"]
```

- [ ] **Step 2: Run tests to verify they fail**

From `platforms/organization-service/`:
Run: `python -m pytest tests/integration/test_organizations_list.py -q`
Expected: FAIL — `test_list_requires_auth` may pass (no route = 405/404? FastAPI returns 405 for POST-only `""` route — the assertion `== 401` fails), the rest fail with non-200/missing route.

- [ ] **Step 3: Implement**

In `schemas/organization.py`, after `OrganizationOut`:

```python
class MyOrganizationOut(OrganizationOut):
    role: str
```

In `service/organization_service.py` (add `OrganizationMember` import at top: `from src.organization.models.member import OrganizationMember`):

```python
def list_organizations_for_user(db: Session, user_id: int) -> list[tuple[Organization, str]]:
    """Organizations where the user is an active member, with their role, by name."""
    return (
        db.query(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .filter(
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
            Organization.deleted_at.is_(None),
        )
        .order_by(Organization.name.asc())
        .all()
    )
```

In `endpoints/organizations.py` (import `MyOrganizationOut` alongside the other schemas); add after `create_organization`:

```python
@router.get("", response_model=list[MyOrganizationOut])
def list_my_organizations(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    rows = organization_service.list_organizations_for_user(db, user_id)
    return [
        MyOrganizationOut(**OrganizationOut.model_validate(org).model_dump(), role=role)
        for org, role in rows
    ]
```

- [ ] **Step 4: Run the service test suite**

Run: `python -m pytest tests/ -q`
Expected: all PASS (new file and the pre-existing suites).

- [ ] **Step 5: Commit**

```bash
git add platforms/organization-service
git commit -m "feat(organization): list my organizations with role

GET /api/v1/organizations returns the caller's active, non-deleted
organizations ordered by name. Needed by the dashboard project picker."
```

---

### Task 2: Dashboard scaffold — Vite + React + TS + Vitest toolchain

**Files:**
- Create: `dashboard/package.json`, `dashboard/vite.config.ts`, `dashboard/tsconfig.json`, `dashboard/eslint.config.js`, `dashboard/index.html`, `dashboard/.gitignore`
- Create: `dashboard/src/main.tsx`, `dashboard/src/App.tsx`, `dashboard/src/index.css`
- Create: `dashboard/src/test/setup.ts`, `dashboard/src/test/server.ts`
- Test: `dashboard/src/App.test.tsx`

**Interfaces:**
- Produces: `npm run dev|build|test|typecheck|lint` all work from `dashboard/`; `App` renders a router (placeholder routes replaced in later tasks); MSW `server` exported from `src/test/server.ts` for all later tests; CSS custom properties (`--status-passed` etc.) defined in `index.css` for later tasks.

- [ ] **Step 1: Create package.json and configs**

`dashboard/package.json`:

```json
{
  "name": "qa-vision-dashboard",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "typecheck": "tsc --noEmit",
    "lint": "eslint src"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.59.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "recharts": "^2.13.0"
  },
  "devDependencies": {
    "@eslint/js": "^9.12.0",
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "eslint": "^9.12.0",
    "jsdom": "^25.0.0",
    "msw": "^2.4.0",
    "typescript": "^5.6.0",
    "typescript-eslint": "^8.8.0",
    "vite": "^5.4.0",
    "vitest": "^2.1.0"
  }
}
```

`dashboard/vite.config.ts`:

```ts
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Local dev against a running stack: the gateway serves the API on 8443.
    proxy: { "/api": { target: "https://localhost:8443", secure: false } },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true,
  },
});
```

`dashboard/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noEmit": true,
    "skipLibCheck": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "vite.config.ts"]
}
```

`dashboard/eslint.config.js`:

```js
import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
);
```

`dashboard/.gitignore`:

```
node_modules
dist
```

`dashboard/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>QA Vision</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: App shell, styles, entry**

`dashboard/src/index.css` (tokens per the dataviz reference palette; light + dark):

```css
:root {
  color-scheme: light;
  --surface-1: #fcfcfb;
  --page: #f9f9f7;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #898781;
  --grid: #e1e0d9;
  --border: rgba(11, 11, 11, 0.1);
  --accent: #2a78d6;
  --status-passed: #0ca30c;
  --status-failed: #d03b3b;
  --status-errored: #ec835a;
  --status-skipped: #898781;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --surface-1: #1a1a19;
    --page: #0d0d0d;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #898781;
    --grid: #2c2c2a;
    --border: rgba(255, 255, 255, 0.1);
    --accent: #3987e5;
  }
}
body {
  margin: 0;
  background: var(--page);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}
.card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
.page { max-width: 1100px; margin: 0 auto; padding: 24px 16px; }
.muted { color: var(--text-muted); }
.error-banner { border: 1px solid var(--status-failed); color: var(--status-failed); border-radius: 8px; padding: 12px 16px; margin: 12px 0; display: flex; gap: 12px; align-items: center; }
table.data { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
table.data th, table.data td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--grid); }
table.data th { color: var(--text-secondary); font-weight: 600; }
.filters { display: flex; gap: 12px; flex-wrap: wrap; align-items: end; margin: 16px 0; }
.filters label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--text-secondary); }
input, select, button { font: inherit; padding: 6px 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-1); color: var(--text-primary); }
button.primary { background: var(--accent); color: #fff; border-color: transparent; cursor: pointer; }
.status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: baseline; }
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--grid); margin: 16px 0; }
.tabs a { padding: 8px 14px; text-decoration: none; color: var(--text-secondary); border-bottom: 2px solid transparent; }
.tabs a.active { color: var(--text-primary); border-bottom-color: var(--accent); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 16px 0; }
.tile-value { font-size: 28px; font-weight: 650; }
.tile-label { font-size: 13px; color: var(--text-secondary); }
```

`dashboard/src/App.tsx` (placeholder; Task 8 replaces the routes):

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="*" element={<h1>QA Vision</h1>} />
      </Routes>
    </BrowserRouter>
  );
}
```

`dashboard/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: 1 } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
```

- [ ] **Step 3: Test infrastructure + first test**

`dashboard/src/test/server.ts`:

```ts
import { setupServer } from "msw/node";

export const server = setupServer();
```

`dashboard/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./server";

// Node's fetch (undici) rejects relative URLs, but the app only uses
// same-origin relative paths. Resolve them against jsdom's origin so MSW
// can intercept them.
const realFetch = globalThis.fetch;
globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
  typeof input === "string" && input.startsWith("/")
    ? realFetch(new URL(input, window.location.origin), init)
    : realFetch(input, init)) as typeof fetch;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  sessionStorage.clear();
});
afterAll(() => server.close());
```

`dashboard/src/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders the app shell", () => {
  render(<App />);
  expect(screen.getByText("QA Vision")).toBeInTheDocument();
});
```

- [ ] **Step 4: Install and verify everything runs**

From `dashboard/`:
Run: `npm install` (generates `package-lock.json` — committed), then `npm run test`, `npm run typecheck`, `npm run lint`, `npm run build`
Expected: test PASS, typecheck clean, lint clean, build emits `dist/`.

- [ ] **Step 5: Commit**

```bash
git add dashboard
git commit -m "feat(dashboard): Vite + React + TypeScript scaffold with Vitest/MSW toolchain"
```

---

### Task 3: Serve the SPA — Dockerfile, compose service, gateway route, smoke checks

**Files:**
- Create: `dashboard/Dockerfile`, `dashboard/nginx.conf`
- Modify: `docker-compose.yml` (new `dashboard` service; gateway `depends_on` gains it)
- Modify: `gateway/nginx.conf.template` (final `location /` proxies to dashboard)
- Modify: `scripts/smoke_gateway.sh` (fall-through expectations change; new dashboard checks)

**Interfaces:**
- Consumes: Task 2's `dashboard/` build.
- Produces: `https://localhost:8443/` serves the SPA; any non-`/api` deep link returns `index.html` (SPA fallback); all existing `/api/*`, `/health*` routes unchanged.

- [ ] **Step 1: Dashboard image**

`dashboard/Dockerfile` (build context is the repo root, matching the other services):

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY dashboard/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
```

`dashboard/nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Hashed build assets may cache forever; index.html must not.
    location /assets/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
        try_files $uri =404;
    }
    location = /index.html {
        add_header Cache-Control "no-cache";
    }
    location / {
        try_files $uri /index.html;
    }
}
```

- [ ] **Step 2: Compose service**

In `docker-compose.yml`, add beside the other `x-*-build` anchors:

```yaml
x-dashboard-build: &dashboard-build
  context: .
  dockerfile: dashboard/Dockerfile
```

Add the service beside the others (nginx has no python, so its healthcheck uses busybox wget inline instead of the shared anchor):

```yaml
  dashboard:
    build: *dashboard-build
    image: qa-vision/dashboard:local
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "http://localhost:80/"]
      interval: 5s
      timeout: 5s
      retries: 12
```

Add `dashboard` to the gateway service's `depends_on` with `condition: service_healthy`, mirroring however the existing upstream services are listed there (read the gateway service block first and copy its exact pattern).

- [ ] **Step 3: Gateway route**

In `gateway/nginx.conf.template`, replace the final block

```nginx
        # ---- everything else ----
        location / {
            return 404;
        }
```

with

```nginx
        # ---- dashboard SPA (everything else) ----
        # The dashboard's own nginx falls unknown paths back to index.html.
        location / {
            limit_req zone=api burst=40 nodelay;
            set $upstream http://dashboard:80;
            proxy_pass $upstream;
        }
```

- [ ] **Step 4: Update the smoke script**

In `scripts/smoke_gateway.sh`: find every check that relied on the old 404 fall-through (e.g. `/metrics`, unknown-path checks) and update it: the gateway now answers 200 with the SPA's HTML there. Keep the security intent: assert the body is the SPA (`<div id="root">`) and does NOT contain Prometheus metric text (`# HELP`). Add dashboard checks using the script's existing `check`/`body_has` helpers:

```bash
# ---- dashboard SPA ----
check "dashboard index" 200 GET "$BASE/"
body_has "dashboard index is the SPA" '<div id="root">'
check "SPA deep link falls back to index" 200 GET "$BASE/projects/1/trends"
body_has "deep link serves the SPA" '<div id="root">'
check "metrics is not exposed" 200 GET "$BASE/metrics"
if grep -q '# HELP' "$TMP/body"; then fail "metrics leaked through the gateway"; else pass "metrics not leaked"; fi
```

- [ ] **Step 5: Verify the stack end to end**

```bash
export SECRET_KEY=dev-secret INTERNAL_API_PASSWORD=dev-internal
docker compose up -d --build --wait gateway dashboard
bash scripts/smoke_gateway.sh
docker compose down -v
```

Expected: every check `ok`, including the new dashboard ones and all pre-existing API checks.

- [ ] **Step 6: Commit**

```bash
git add dashboard/Dockerfile dashboard/nginx.conf docker-compose.yml gateway/nginx.conf.template scripts/smoke_gateway.sh
git commit -m "feat(dashboard): serve the SPA through the gateway

New dashboard container (static nginx) behind the gateway's catch-all
location; SPA fallback for deep links; smoke checks updated for the new
fall-through behavior."
```

---

### Task 4: Token store and HTTP client with silent refresh

**Files:**
- Create: `dashboard/src/auth/tokens.ts`, `dashboard/src/api/http.ts`
- Test: `dashboard/src/api/http.test.ts`

**Interfaces:**
- Produces:
  - `tokens.ts`: `setTokens(access: string, refresh: string): void`, `getAccessToken(): string | null`, `getRefreshToken(): string | null`, `clearTokens(): void`, `isAuthenticated(): boolean` (refresh token present).
  - `http.ts`: `class ApiError extends Error { status: number; detail: string }`, `apiFetch<T>(path: string, init?: RequestInit): Promise<T>`, `setOnAuthFailure(fn: () => void): void`, `buildQuery(params: Record<string, string | number | undefined | null>): string` (skips undefined/null/empty-string; returns `""` or `?a=1&b=x`, values URL-encoded).

- [ ] **Step 1: Write the failing tests**

`dashboard/src/api/http.test.ts`:

```ts
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens, clearTokens, getRefreshToken } from "../auth/tokens";
import { apiFetch, ApiError, buildQuery, setOnAuthFailure } from "./http";

afterEach(() => clearTokens());

test("buildQuery skips empty values and encodes", () => {
  expect(buildQuery({ days: 30, branch: undefined, search: "" })).toBe("?days=30");
  expect(buildQuery({ q: "a b/c" })).toBe("?q=a%20b%2Fc");
  expect(buildQuery({})).toBe("");
});

test("sends bearer token and parses JSON", async () => {
  setTokens("acc-1", "ref-1");
  server.use(
    http.get("/api/v1/thing", ({ request }) => {
      expect(request.headers.get("Authorization")).toBe("Bearer acc-1");
      return HttpResponse.json({ ok: true });
    }),
  );
  await expect(apiFetch("/api/v1/thing")).resolves.toEqual({ ok: true });
});

test("401 triggers one refresh then retries; concurrent calls share the refresh", async () => {
  setTokens("stale", "ref-1");
  let refreshes = 0;
  server.use(
    http.get("/api/v1/thing", ({ request }) =>
      request.headers.get("Authorization") === "Bearer fresh"
        ? HttpResponse.json({ ok: true })
        : new HttpResponse(null, { status: 401 }),
    ),
    http.post("/api/v1/auth/refresh-token", async ({ request }) => {
      refreshes += 1;
      expect(await request.json()).toEqual({ refresh_token: "ref-1" });
      return HttpResponse.json({ access_token: "fresh", refresh_token: "ref-2", token_type: "bearer" });
    }),
  );
  const [a, b] = await Promise.all([apiFetch("/api/v1/thing"), apiFetch("/api/v1/thing")]);
  expect(a).toEqual({ ok: true });
  expect(b).toEqual({ ok: true });
  expect(refreshes).toBe(1);
  expect(getRefreshToken()).toBe("ref-2"); // rotation stored
});

test("failed refresh clears tokens and calls onAuthFailure", async () => {
  setTokens("stale", "dead");
  const onFail = vi.fn();
  setOnAuthFailure(onFail);
  server.use(
    http.get("/api/v1/thing", () => new HttpResponse(null, { status: 401 })),
    http.post("/api/v1/auth/refresh-token", () => new HttpResponse(null, { status: 401 })),
  );
  await expect(apiFetch("/api/v1/thing")).rejects.toMatchObject({ status: 401 });
  expect(onFail).toHaveBeenCalled();
  expect(getRefreshToken()).toBeNull();
});

test("non-JSON error body becomes a readable ApiError", async () => {
  setTokens("acc", "ref");
  server.use(
    http.get("/api/v1/thing", () => new HttpResponse("<html>Bad Gateway</html>", { status: 502 })),
  );
  const err = await apiFetch("/api/v1/thing").catch((e) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect(err.status).toBe(502);
  expect(err.detail).toMatch(/502/);
});

test("JSON error detail is surfaced", async () => {
  setTokens("acc", "ref");
  server.use(
    http.get("/api/v1/thing", () =>
      HttpResponse.json({ detail: "Project not found" }, { status: 404 }),
    ),
  );
  await expect(apiFetch("/api/v1/thing")).rejects.toMatchObject({ detail: "Project not found" });
});
```

- [ ] **Step 2: Run tests to verify they fail**

From `dashboard/`:
Run: `npx vitest run src/api/http.test.ts`
Expected: FAIL — modules don't exist.

- [ ] **Step 3: Implement**

`dashboard/src/auth/tokens.ts`:

```ts
const REFRESH_KEY = "qav.refresh";
let accessToken: string | null = null;

export function setTokens(access: string, refresh: string): void {
  accessToken = access;
  sessionStorage.setItem(REFRESH_KEY, refresh);
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_KEY);
}

export function clearTokens(): void {
  accessToken = null;
  sessionStorage.removeItem(REFRESH_KEY);
}

export function isAuthenticated(): boolean {
  return getRefreshToken() !== null;
}
```

`dashboard/src/api/http.ts`:

```ts
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "../auth/tokens";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

let onAuthFailure: () => void = () => {};
export function setOnAuthFailure(fn: () => void): void {
  onAuthFailure = fn;
}

export function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    q.set(key, String(value));
  }
  const s = q.toString();
  // URLSearchParams encodes spaces as "+"; normalize to %20 so paths and
  // params read the same everywhere.
  return s ? `?${s.replaceAll("+", "%20")}` : "";
}

async function errorFrom(response: Response): Promise<ApiError> {
  let detail = `Request failed with status ${response.status}`;
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") detail = body.detail;
  } catch {
    // non-JSON body (gateway HTML error page): keep the generic detail
  }
  return new ApiError(response.status, detail);
}

// A single in-flight refresh shared by every 401 that hits while it runs.
let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  const response = await fetch("/api/v1/auth/refresh-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!response.ok) return false;
  const body = await response.json();
  setTokens(body.access_token, body.refresh_token);
  return true;
}

async function rawFetch(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return fetch(path, { ...init, headers });
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response = await rawFetch(path, init);

  if (response.status === 401) {
    refreshing ??= refreshTokens().finally(() => {
      refreshing = null;
    });
    const refreshed = await refreshing;
    if (!refreshed) {
      clearTokens();
      onAuthFailure();
      throw new ApiError(401, "Session expired");
    }
    response = await rawFetch(path, init);
  }

  if (!response.ok) throw await errorFrom(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/api/http.test.ts` then `npm run typecheck && npm run lint`
Expected: PASS, clean.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/auth/tokens.ts dashboard/src/api/http.ts dashboard/src/api/http.test.ts
git commit -m "feat(dashboard): HTTP client with bearer auth and shared silent refresh"
```

---

### Task 5: Auth API, login page, route guard, logout

**Files:**
- Create: `dashboard/src/api/auth.ts`, `dashboard/src/pages/LoginPage.tsx`, `dashboard/src/components/RequireAuth.tsx`, `dashboard/src/components/ErrorBanner.tsx`
- Test: `dashboard/src/pages/LoginPage.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `setTokens`, `clearTokens`, `isAuthenticated` (Task 4).
- Produces:
  - `auth.ts`: `login(email: string, password: string): Promise<void>` (stores tokens), `logout(): Promise<void>` (best-effort POST logout, always clears tokens).
  - `RequireAuth`: `<RequireAuth>{children}</RequireAuth>` — redirects to `/login` when `isAuthenticated()` is false.
  - `ErrorBanner`: `({ error, onRetry }: { error: unknown; onRetry?: () => void })` — renders `.error-banner` with the `ApiError.detail` or a generic message, optional Retry button. Used by every view.

- [ ] **Step 1: Write the failing tests**

`dashboard/src/pages/LoginPage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { getRefreshToken } from "../auth/tokens";
import LoginPage from "./LoginPage";

function renderLogin() {
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<div>PICKER</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

test("successful login stores tokens and navigates home", async () => {
  server.use(
    http.post("/api/v1/auth/login", async ({ request }) => {
      expect(await request.json()).toEqual({ email: "a@b.co", password: "pw" });
      return HttpResponse.json({ access_token: "acc", refresh_token: "ref", token_type: "bearer" });
    }),
  );
  renderLogin();
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.co");
  await userEvent.type(screen.getByLabelText(/password/i), "pw");
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
  expect(await screen.findByText("PICKER")).toBeInTheDocument();
  expect(getRefreshToken()).toBe("ref");
});

test("bad credentials show the API detail", async () => {
  server.use(
    http.post("/api/v1/auth/login", () =>
      HttpResponse.json({ detail: "Incorrect email or password" }, { status: 401 }),
    ),
  );
  renderLogin();
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.co");
  await userEvent.type(screen.getByLabelText(/password/i), "nope");
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
  expect(await screen.findByText("Incorrect email or password")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/pages/LoginPage.test.tsx`
Expected: FAIL — modules don't exist.

- [ ] **Step 3: Implement**

`dashboard/src/api/auth.ts`:

```ts
import { apiFetch } from "./http";
import { clearTokens, getRefreshToken, setTokens } from "../auth/tokens";

interface TokenOut {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export async function login(email: string, password: string): Promise<void> {
  const tokens = await apiFetch<TokenOut>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setTokens(tokens.access_token, tokens.refresh_token);
}

export async function logout(): Promise<void> {
  const refresh = getRefreshToken();
  try {
    if (refresh) {
      await apiFetch("/api/v1/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refresh }),
      });
    }
  } finally {
    clearTokens();
  }
}
```

`dashboard/src/components/ErrorBanner.tsx`:

```tsx
import { ApiError } from "../api/http";

export default function ErrorBanner({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const detail =
    error instanceof ApiError
      ? error.status === 429
        ? "Too many requests — please retry shortly."
        : error.detail
      : "Something went wrong.";
  return (
    <div className="error-banner" role="alert">
      <span>{detail}</span>
      {onRetry && <button onClick={onRetry}>Retry</button>}
    </div>
  );
}
```

`dashboard/src/components/RequireAuth.tsx`:

```tsx
import { Navigate } from "react-router-dom";
import { isAuthenticated } from "../auth/tokens";

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
```

`dashboard/src/pages/LoginPage.tsx`:

```tsx
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/auth";
import ErrorBanner from "../components/ErrorBanner";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 380 }}>
      <h1>QA Vision</h1>
      <form className="card" onSubmit={onSubmit}>
        <p>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
        </p>
        <p>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
        </p>
        {error != null && <ErrorBanner error={error} />}
        <button className="primary" type="submit" disabled={busy}>
          Sign in
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 4: Run tests, typecheck, lint**

Run: `npm run test && npm run typecheck && npm run lint`
Expected: all PASS (App test still green).

- [ ] **Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat(dashboard): login page, auth API, route guard and error banner"
```

---

### Task 6: Organizations/projects API + picker page

**Files:**
- Create: `dashboard/src/api/orgs.ts`, `dashboard/src/pages/PickerPage.tsx`
- Test: `dashboard/src/pages/PickerPage.test.tsx`

**Interfaces:**
- Consumes: `apiFetch` (Task 4), Task 1's endpoint shape.
- Produces:
  - `orgs.ts`: `interface MyOrganization { id: number; name: string; slug: string; role: string }`, `interface Project { id: number; name: string }`, `listMyOrganizations(): Promise<MyOrganization[]>`, `listProjects(orgId: number): Promise<Project[]>`.
  - `PickerPage`: lists orgs; selecting one lists its projects; clicking a project navigates to `/projects/{id}/trends`. Empty states for zero orgs ("You are not a member of any organization yet") and zero projects.

- [ ] **Step 1: Write the failing tests**

`dashboard/src/pages/PickerPage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens } from "../auth/tokens";
import PickerPage from "./PickerPage";

function renderPicker() {
  setTokens("acc", "ref");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<PickerPage />} />
          <Route path="/projects/:projectId/trends" element={<div>TRENDS</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const org = { id: 1, name: "Acme", slug: "acme", role: "owner", plan_tier: "free", created_at: "2026-01-01T00:00:00Z", updated_at: null };

test("zero organizations shows an empty state", async () => {
  server.use(http.get("/api/v1/organizations", () => HttpResponse.json([])));
  renderPicker();
  expect(await screen.findByText(/not a member of any organization/i)).toBeInTheDocument();
});

test("selecting an org lists projects; clicking navigates to trends", async () => {
  server.use(
    http.get("/api/v1/organizations", () => HttpResponse.json([org])),
    http.get("/api/v1/organizations/1/projects", () =>
      HttpResponse.json([{ id: 42, name: "Web Tests" }]),
    ),
  );
  renderPicker();
  await userEvent.click(await screen.findByText("Acme"));
  await userEvent.click(await screen.findByText("Web Tests"));
  expect(await screen.findByText("TRENDS")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/pages/PickerPage.test.tsx`
Expected: FAIL — modules don't exist.

- [ ] **Step 3: Implement**

`dashboard/src/api/orgs.ts`:

```ts
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
```

`dashboard/src/pages/PickerPage.tsx`:

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listMyOrganizations, listProjects } from "../api/orgs";
import ErrorBanner from "../components/ErrorBanner";

export default function PickerPage() {
  const [orgId, setOrgId] = useState<number | null>(null);
  const orgs = useQuery({ queryKey: ["orgs"], queryFn: listMyOrganizations });
  const projects = useQuery({
    queryKey: ["projects", orgId],
    queryFn: () => listProjects(orgId!),
    enabled: orgId !== null,
  });

  return (
    <div className="page">
      <h1>Choose a project</h1>
      {orgs.error != null && <ErrorBanner error={orgs.error} onRetry={() => orgs.refetch()} />}
      {orgs.isPending && <p className="muted">Loading organizations…</p>}
      {orgs.data?.length === 0 && (
        <p className="muted">You are not a member of any organization yet.</p>
      )}
      <div style={{ display: "flex", gap: 24 }}>
        <ul>
          {orgs.data?.map((org) => (
            <li key={org.id}>
              <button onClick={() => setOrgId(org.id)}>{org.name}</button>{" "}
              <span className="muted">{org.role}</span>
            </li>
          ))}
        </ul>
        {orgId !== null && (
          <div>
            {projects.error != null && (
              <ErrorBanner error={projects.error} onRetry={() => projects.refetch()} />
            )}
            {projects.isPending && <p className="muted">Loading projects…</p>}
            {projects.data?.length === 0 && <p className="muted">No projects in this organization.</p>}
            <ul>
              {projects.data?.map((project) => (
                <li key={project.id}>
                  <Link to={`/projects/${project.id}/trends`}>{project.name}</Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests, typecheck, lint**

Run: `npm run test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat(dashboard): organization and project picker"
```

---

### Task 7: Analytics API client and types

**Files:**
- Create: `dashboard/src/api/analytics.ts`
- Test: `dashboard/src/api/analytics.test.ts`

**Interfaces:**
- Consumes: `apiFetch`, `buildQuery` (Task 4).
- Produces (types mirror `platforms/ingestion-service/src/ingestion/schemas/analytics.py`):

```ts
export interface TrendDay {
  date: string; runs: number; total: number; passed: number; failed: number;
  errored: number; skipped: number; pass_rate: number | null;
  avg_run_duration_ms: number | null; max_run_duration_ms: number | null;
}
export interface Trends { tz: string; days: TrendDay[] }
export interface StatsRow {
  test_key: string; suite: string; class_name: string; name: string;
  runs: number; passed: number; failed: number; errored: number; skipped: number;
  pass_rate: number | null; avg_duration_ms: number | null;
  last_status: string; last_seen: string;
}
export interface Execution {
  run_id: number; started_at: string; branch: string | null; commit_sha: string | null;
  environment: string | null; status: string; duration_ms: number; message: string | null;
}
export interface History {
  test_key: string; suite: string; class_name: string; name: string;
  summary: { runs: number; passed: number; failed: number; errored: number; skipped: number; pass_rate: number | null; avg_duration_ms: number | null };
  executions: Execution[];
}
export interface CommitRef { commit_sha: string; environment: string | null }
export interface FlakyRow {
  test_key: string; suite: string; class_name: string; name: string;
  reason: "same_commit" | "flips"; commits: CommitRef[];
  flips: number | null; flip_rate: number | null;
  runs: number; last_status: string; last_seen: string;
}
```

  and functions:
  - `getTrends(projectId: number, opts: { days: number; tz: string; branch?: string; environment?: string }): Promise<Trends>`
  - `getTests(projectId: number, opts: { days: number; sort: "failures" | "duration" | "name"; search?: string; limit: number; offset: number }): Promise<StatsRow[]>`
  - `getHistory(projectId: number, testKey: string, opts: { days: number; branch?: string; limit: number }): Promise<History>`
  - `getFlaky(projectId: number, opts: { windowDays: number; minRuns: number; minFlipRate: number; branch?: string }): Promise<FlakyRow[]>`
  - `formatPassRate(rate: number | null): string` — `0.9876 → "98.8%"`, `null → "—"`.
  - `formatDuration(ms: number | null): string` — `null → "—"`, `<1000 → "640 ms"`, else seconds with one decimal `"2.5 s"`, `>=60s → "1m 05s"`.

- [ ] **Step 1: Write the failing tests**

`dashboard/src/api/analytics.test.ts`:

```ts
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens } from "../auth/tokens";
import { getFlaky, getHistory, getTests, getTrends, formatDuration, formatPassRate } from "./analytics";

beforeEach(() => setTokens("acc", "ref"));

test("getTrends maps options to query params", async () => {
  let url = "";
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", ({ request }) => {
      url = request.url;
      return HttpResponse.json({ tz: "UTC", days: [] });
    }),
  );
  await getTrends(42, { days: 30, tz: "Europe/London", branch: "main" });
  const params = new URL(url).searchParams;
  expect(params.get("days")).toBe("30");
  expect(params.get("tz")).toBe("Europe/London");
  expect(params.get("branch")).toBe("main");
  expect(params.has("environment")).toBe(false);
});

test("getTests maps sort/search/pagination", async () => {
  let url = "";
  server.use(
    http.get("/api/v1/projects/42/analytics/tests", ({ request }) => {
      url = request.url;
      return HttpResponse.json([]);
    }),
  );
  await getTests(42, { days: 14, sort: "duration", search: "login", limit: 50, offset: 100 });
  const params = new URL(url).searchParams;
  expect(params.get("sort")).toBe("duration");
  expect(params.get("search")).toBe("login");
  expect(params.get("limit")).toBe("50");
  expect(params.get("offset")).toBe("100");
});

test("getHistory URL-encodes the test key", async () => {
  const key = "tests/test_login.py::TestLogin::test_ok";
  let hit = false;
  server.use(
    http.get(`/api/v1/projects/42/analytics/tests/${encodeURIComponent(key)}/history`, () => {
      hit = true;
      return HttpResponse.json({
        test_key: key, suite: "s", class_name: "c", name: "n",
        summary: { runs: 0, passed: 0, failed: 0, errored: 0, skipped: 0, pass_rate: null, avg_duration_ms: null },
        executions: [],
      });
    }),
  );
  await getHistory(42, key, { days: 30, limit: 100 });
  expect(hit).toBe(true);
});

test("getFlaky maps snake_case params", async () => {
  let url = "";
  server.use(
    http.get("/api/v1/projects/42/analytics/flaky", ({ request }) => {
      url = request.url;
      return HttpResponse.json([]);
    }),
  );
  await getFlaky(42, { windowDays: 14, minRuns: 5, minFlipRate: 0.3 });
  const params = new URL(url).searchParams;
  expect(params.get("window_days")).toBe("14");
  expect(params.get("min_runs")).toBe("5");
  expect(params.get("min_flip_rate")).toBe("0.3");
});

test("formatters", () => {
  expect(formatPassRate(0.9876)).toBe("98.8%");
  expect(formatPassRate(null)).toBe("—");
  expect(formatDuration(640)).toBe("640 ms");
  expect(formatDuration(2500)).toBe("2.5 s");
  expect(formatDuration(65000)).toBe("1m 05s");
  expect(formatDuration(null)).toBe("—");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/api/analytics.test.ts`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

`dashboard/src/api/analytics.ts` — the interfaces from the Produces block above, plus:

```ts
import { apiFetch, buildQuery } from "./http";

// (interfaces from the Produces block go here, exported)

export function getTrends(
  projectId: number,
  opts: { days: number; tz: string; branch?: string; environment?: string },
): Promise<Trends> {
  const q = buildQuery({ days: opts.days, tz: opts.tz, branch: opts.branch, environment: opts.environment });
  return apiFetch(`/api/v1/projects/${projectId}/analytics/trends${q}`);
}

export function getTests(
  projectId: number,
  opts: { days: number; sort: "failures" | "duration" | "name"; search?: string; limit: number; offset: number },
): Promise<StatsRow[]> {
  const q = buildQuery({ days: opts.days, sort: opts.sort, search: opts.search, limit: opts.limit, offset: opts.offset });
  return apiFetch(`/api/v1/projects/${projectId}/analytics/tests${q}`);
}

export function getHistory(
  projectId: number,
  testKey: string,
  opts: { days: number; branch?: string; limit: number },
): Promise<History> {
  const q = buildQuery({ days: opts.days, branch: opts.branch, limit: opts.limit });
  return apiFetch(`/api/v1/projects/${projectId}/analytics/tests/${encodeURIComponent(testKey)}/history${q}`);
}

export function getFlaky(
  projectId: number,
  opts: { windowDays: number; minRuns: number; minFlipRate: number; branch?: string },
): Promise<FlakyRow[]> {
  const q = buildQuery({
    window_days: opts.windowDays,
    min_runs: opts.minRuns,
    min_flip_rate: opts.minFlipRate,
    branch: opts.branch,
  });
  return apiFetch(`/api/v1/projects/${projectId}/analytics/flaky${q}`);
}

export function formatPassRate(rate: number | null): string {
  if (rate === null) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}

export function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes}m ${String(rest).padStart(2, "0")}s`;
}
```

- [ ] **Step 4: Run tests, typecheck, lint**

Run: `npm run test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/api
git commit -m "feat(dashboard): typed analytics API client"
```

---

### Task 8: Router wiring and project layout shell

**Files:**
- Modify: `dashboard/src/App.tsx`
- Create: `dashboard/src/pages/ProjectLayout.tsx`, `dashboard/src/components/StatusDot.tsx`
- Create (placeholder views replaced by Tasks 9–12): `dashboard/src/pages/TrendsPage.tsx`, `dashboard/src/pages/TestsPage.tsx`, `dashboard/src/pages/HistoryPage.tsx`, `dashboard/src/pages/FlakyPage.tsx`
- Test: `dashboard/src/App.routing.test.tsx`

**Interfaces:**
- Consumes: `RequireAuth`, `LoginPage`, `PickerPage`, `logout`, `setOnAuthFailure`.
- Produces: route table (exact paths) —
  - `/login` → `LoginPage`
  - `/` → `RequireAuth > PickerPage`
  - `/projects/:projectId` → `RequireAuth > ProjectLayout` with children: index → redirect `trends`; `trends` → `TrendsPage`; `tests` → `TestsPage`; `tests/:testKey` → `HistoryPage`; `flaky` → `FlakyPage`.
  - `ProjectLayout` renders tabs (Trends / Tests / Flaky), a "Switch project" link to `/`, a "Sign out" button (calls `logout()` then navigates `/login`), and an `<Outlet />`. It reads `projectId` via `useParams` — children read it the same way.
  - `StatusDot`: `({ status }: { status: string })` — colored dot (CSS var by status) followed by the status text. Never color alone.
  - Each placeholder page default-exports a component rendering its name (e.g. `<h2>Trends</h2>`); Tasks 9–12 replace them.

- [ ] **Step 1: Write the failing test**

`dashboard/src/App.routing.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { setTokens, clearTokens } from "./auth/tokens";
import { AppRoutes } from "./App";
import { MemoryRouter } from "react-router-dom";

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, enabled: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("unauthenticated project route redirects to login", () => {
  clearTokens();
  renderAt("/projects/42/trends");
  expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
});

test("project index redirects to trends tab", async () => {
  setTokens("acc", "ref");
  renderAt("/projects/42");
  expect(await screen.findByRole("heading", { name: /trends/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/App.routing.test.tsx`
Expected: FAIL — `AppRoutes` not exported, pages missing.

- [ ] **Step 3: Implement**

Each placeholder page, e.g. `dashboard/src/pages/TrendsPage.tsx`:

```tsx
export default function TrendsPage() {
  return <h2>Trends</h2>;
}
```

(same shape for `TestsPage`, `HistoryPage`, `FlakyPage` with their names).

`dashboard/src/components/StatusDot.tsx`:

```tsx
const COLOR: Record<string, string> = {
  passed: "var(--status-passed)",
  failed: "var(--status-failed)",
  errored: "var(--status-errored)",
  skipped: "var(--status-skipped)",
};

export default function StatusDot({ status }: { status: string }) {
  return (
    <span>
      <span className="status-dot" style={{ background: COLOR[status] ?? "var(--text-muted)" }} />
      {status}
    </span>
  );
}
```

`dashboard/src/pages/ProjectLayout.tsx`:

```tsx
import { Link, NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { logout } from "../api/auth";

export default function ProjectLayout() {
  const { projectId } = useParams();
  const navigate = useNavigate();

  async function onSignOut() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Project {projectId}</h1>
        <span>
          <Link to="/">Switch project</Link>{" "}
          <button onClick={onSignOut}>Sign out</button>
        </span>
      </div>
      <nav className="tabs">
        <NavLink to="trends" className={({ isActive }) => (isActive ? "active" : "")}>Trends</NavLink>
        <NavLink to="tests" end className={({ isActive }) => (isActive ? "active" : "")}>Tests</NavLink>
        <NavLink to="flaky" className={({ isActive }) => (isActive ? "active" : "")}>Flaky</NavLink>
      </nav>
      <Outlet />
    </div>
  );
}
```

`dashboard/src/App.tsx` (full replacement):

```tsx
import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { setOnAuthFailure } from "./api/http";
import RequireAuth from "./components/RequireAuth";
import LoginPage from "./pages/LoginPage";
import PickerPage from "./pages/PickerPage";
import ProjectLayout from "./pages/ProjectLayout";
import TrendsPage from "./pages/TrendsPage";
import TestsPage from "./pages/TestsPage";
import HistoryPage from "./pages/HistoryPage";
import FlakyPage from "./pages/FlakyPage";

export function AppRoutes() {
  const navigate = useNavigate();
  useEffect(() => {
    setOnAuthFailure(() => navigate("/login", { replace: true }));
  }, [navigate]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RequireAuth><PickerPage /></RequireAuth>} />
      <Route path="/projects/:projectId" element={<RequireAuth><ProjectLayout /></RequireAuth>}>
        <Route index element={<Navigate to="trends" replace />} />
        <Route path="trends" element={<TrendsPage />} />
        <Route path="tests" element={<TestsPage />} />
        <Route path="tests/:testKey" element={<HistoryPage />} />
        <Route path="flaky" element={<FlakyPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
```

Update `dashboard/src/App.test.tsx` — the shell now needs a QueryClientProvider and shows the login page when logged out:

```tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";

test("renders the app shell (login when logged out)", () => {
  const qc = new QueryClient();
  render(
    <QueryClientProvider client={qc}>
      <App />
    </QueryClientProvider>,
  );
  expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
});
```

- [ ] **Step 4: Run tests, typecheck, lint**

Run: `npm run test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat(dashboard): router wiring and project layout with tabs"
```

---

### Task 9: Trends view

**Files:**
- Modify: `dashboard/src/pages/TrendsPage.tsx` (replace placeholder)
- Create: `dashboard/src/components/FilterBar.tsx`
- Test: `dashboard/src/pages/TrendsPage.test.tsx`

**Interfaces:**
- Consumes: `getTrends`, `formatPassRate`, `formatDuration`, `ErrorBanner`.
- Produces: `FilterBar` — `({ children }: { children: React.ReactNode })` renders `.filters`; reused by Tasks 10–12.

**Chart rules (dataviz):** one axis per chart — the counts chart and the pass-rate chart are separate stacked panels, never dual-axis. Status colors from the CSS tokens; legend present; tooltips on hover; a "View data" toggle renders the same days as a table (the accessible/table view). Null `pass_rate` points are gaps (`connectNulls={false}`), not zeros.

- [ ] **Step 1: Write the failing tests**

`dashboard/src/pages/TrendsPage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens } from "../auth/tokens";
import TrendsPage from "./TrendsPage";

const day = (date: string, passed: number, failed: number, pass_rate: number | null) => ({
  date, runs: 2, total: passed + failed, passed, failed,
  errored: 0, skipped: 0, pass_rate, avg_run_duration_ms: 1200, max_run_duration_ms: 3000,
});

function renderTrends() {
  setTokens("acc", "ref");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/trends"]}>
        <Routes>
          <Route path="/projects/:projectId/trends" element={<TrendsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders stat tiles and the data table with null pass_rate as em dash", async () => {
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", () =>
      HttpResponse.json({ tz: "UTC", days: [day("2026-09-29", 8, 2, 0.8), day("2026-09-30", 0, 0, null)] }),
    ),
  );
  renderTrends();
  await userEvent.click(await screen.findByRole("button", { name: /view data/i }));
  expect(screen.getByText("2026-09-30")).toBeInTheDocument();
  expect(screen.getAllByText("—").length).toBeGreaterThan(0); // null pass_rate rendered as em dash
  expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
});

test("empty window shows an empty state naming the filters", async () => {
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", () =>
      HttpResponse.json({ tz: "UTC", days: [] }),
    ),
  );
  renderTrends();
  expect(await screen.findByText(/no runs in the last 30 days/i)).toBeInTheDocument();
});

test("changing days refetches with the new value", async () => {
  const seen: string[] = [];
  server.use(
    http.get("/api/v1/projects/42/analytics/trends", ({ request }) => {
      seen.push(new URL(request.url).searchParams.get("days")!);
      return HttpResponse.json({ tz: "UTC", days: [] });
    }),
  );
  renderTrends();
  await screen.findByText(/no runs/i);
  await userEvent.selectOptions(screen.getByLabelText(/days/i), "90");
  await screen.findByText(/no runs in the last 90 days/i);
  expect(seen).toContain("90");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/pages/TrendsPage.test.tsx`
Expected: FAIL — placeholder page has none of this.

- [ ] **Step 3: Implement**

`dashboard/src/components/FilterBar.tsx`:

```tsx
export default function FilterBar({ children }: { children: React.ReactNode }) {
  return <div className="filters">{children}</div>;
}
```

`dashboard/src/pages/TrendsPage.tsx`:

```tsx
import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { formatDuration, formatPassRate, getTrends } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";

const STATUS = [
  { key: "passed", label: "Passed", color: "var(--status-passed)" },
  { key: "failed", label: "Failed", color: "var(--status-failed)" },
  { key: "errored", label: "Errored", color: "var(--status-errored)" },
  { key: "skipped", label: "Skipped", color: "var(--status-skipped)" },
] as const;

export default function TrendsPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const [days, setDays] = useState(30);
  const [branch, setBranch] = useState("");
  const [environment, setEnvironment] = useState("");
  const [showTable, setShowTable] = useState(false);

  const query = useQuery({
    queryKey: ["trends", id, days, branch, environment],
    queryFn: () => getTrends(id, { days, tz, branch: branch || undefined, environment: environment || undefined }),
  });

  const trendDays = query.data?.days ?? [];
  const totals = trendDays.reduce(
    (acc, d) => ({
      runs: acc.runs + d.runs,
      passed: acc.passed + d.passed,
      counted: acc.counted + d.passed + d.failed + d.errored,
    }),
    { runs: 0, passed: 0, counted: 0 },
  );
  const windowRate = totals.counted > 0 ? totals.passed / totals.counted : null;
  const rateData = trendDays.map((d) => ({
    date: d.date,
    ratePct: d.pass_rate === null ? null : d.pass_rate * 100,
  }));

  return (
    <section>
      <FilterBar>
        <label>
          Days
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>7</option>
            <option value={30}>30</option>
            <option value={90}>90</option>
          </select>
        </label>
        <label>
          Branch
          <input value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="all" />
        </label>
        <label>
          Environment
          <input value={environment} onChange={(e) => setEnvironment(e.target.value)} placeholder="all" />
        </label>
        <button onClick={() => setShowTable((v) => !v)}>
          {showTable ? "Hide data" : "View data"}
        </button>
      </FilterBar>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading trends…</p>}
      {query.data && trendDays.length === 0 && (
        <p className="muted">
          No runs in the last {days} days{branch && ` on ${branch}`}{environment && ` in ${environment}`}.
        </p>
      )}

      {trendDays.length > 0 && (
        <>
          <div className="tiles">
            <div className="card">
              <div className="tile-value">{totals.runs}</div>
              <div className="tile-label">Runs ({days} days)</div>
            </div>
            <div className="card">
              <div className="tile-value">{formatPassRate(windowRate)}</div>
              <div className="tile-label">Pass rate ({days} days)</div>
            </div>
            <div className="card">
              <div className="tile-value">
                {formatDuration(trendDays[trendDays.length - 1].avg_run_duration_ms)}
              </div>
              <div className="tile-label">Avg run duration (last day)</div>
            </div>
          </div>

          <div className="card">
            <h3>Results per day</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={trendDays} barCategoryGap="20%">
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="date" stroke="var(--text-muted)" tickLine={false} />
                <YAxis allowDecimals={false} stroke="var(--text-muted)" tickLine={false} />
                <Tooltip />
                <Legend />
                {STATUS.map((s, i) => (
                  <Bar
                    key={s.key}
                    dataKey={s.key}
                    name={s.label}
                    stackId="status"
                    fill={s.color}
                    stroke="var(--surface-1)"
                    strokeWidth={1}
                    radius={i === STATUS.length - 1 ? [4, 4, 0, 0] : undefined}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card" style={{ marginTop: 12 }}>
            <h3>Pass rate</h3>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={rateData}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="date" stroke="var(--text-muted)" tickLine={false} />
                <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} stroke="var(--text-muted)" tickLine={false} />
                <Tooltip formatter={(v) => [`${Number(v).toFixed(1)}%`, "Pass rate"]} />
                <Line dataKey="ratePct" stroke="var(--accent)" strokeWidth={2} dot={false} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {showTable && query.data && (
        <div className="card" style={{ marginTop: 12 }}>
          <table className="data">
            <thead>
              <tr>
                <th>Date</th><th>Runs</th><th>Passed</th><th>Failed</th>
                <th>Errored</th><th>Skipped</th><th>Pass rate</th><th>Avg duration</th>
              </tr>
            </thead>
            <tbody>
              {trendDays.map((d) => (
                <tr key={d.date}>
                  <td>{d.date}</td><td>{d.runs}</td><td>{d.passed}</td><td>{d.failed}</td>
                  <td>{d.errored}</td><td>{d.skipped}</td>
                  <td>{formatPassRate(d.pass_rate)}</td>
                  <td>{formatDuration(d.avg_run_duration_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
```

Note: Recharts renders SVG via jsdom only partially — the tests assert tiles, table, empty state, and refetch, not SVG internals. Visual check happens in Task 13's stack run.

- [ ] **Step 4: Run tests, typecheck, lint**

Run: `npm run test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat(dashboard): trends view with stat tiles, status bars and pass-rate chart"
```

---

### Task 10: Tests table view

**Files:**
- Modify: `dashboard/src/pages/TestsPage.tsx` (replace placeholder)
- Test: `dashboard/src/pages/TestsPage.test.tsx`

**Interfaces:**
- Consumes: `getTests`, `formatPassRate`, `formatDuration`, `StatusDot`, `FilterBar`, `ErrorBanner`.
- Produces: rows link to `tests/{encodeURIComponent(test_key)}` (relative to the project layout).

- [ ] **Step 1: Write the failing tests**

`dashboard/src/pages/TestsPage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens } from "../auth/tokens";
import TestsPage from "./TestsPage";

const row = (key: string, name: string) => ({
  test_key: key, suite: "auth", class_name: "TestLogin", name,
  runs: 10, passed: 9, failed: 1, errored: 0, skipped: 0,
  pass_rate: 0.9, avg_duration_ms: 420, last_status: "failed", last_seen: "2026-09-30T10:00:00Z",
});

function renderTests() {
  setTokens("acc", "ref");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/tests"]}>
        <Routes>
          <Route path="/projects/:projectId/tests" element={<TestsPage />} />
          <Route path="/projects/:projectId/tests/:testKey" element={<div>HISTORY</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders rows; clicking a test navigates to its encoded history route", async () => {
  server.use(
    http.get("/api/v1/projects/42/analytics/tests", () =>
      HttpResponse.json([row("tests/a.py::TestLogin::test_ok", "test_ok")]),
    ),
  );
  renderTests();
  await userEvent.click(await screen.findByText("test_ok"));
  expect(await screen.findByText("HISTORY")).toBeInTheDocument();
});

test("search and sort map to params; next page advances offset", async () => {
  const calls: URLSearchParams[] = [];
  server.use(
    http.get("/api/v1/projects/42/analytics/tests", ({ request }) => {
      calls.push(new URL(request.url).searchParams);
      // A full page signals that "Next" should be enabled.
      return HttpResponse.json(Array.from({ length: 50 }, (_, i) => row(`k${i}`, `t${i}`)));
    }),
  );
  renderTests();
  await screen.findByText("t0");
  await userEvent.selectOptions(screen.getByLabelText(/sort/i), "duration");
  await userEvent.type(screen.getByLabelText(/search/i), "login");
  await userEvent.click(screen.getByRole("button", { name: /apply/i }));
  await userEvent.click(await screen.findByRole("button", { name: /next/i }));
  const last = calls[calls.length - 1];
  expect(last.get("sort")).toBe("duration");
  expect(last.get("search")).toBe("login");
  expect(last.get("offset")).toBe("50");
});

test("empty result shows an empty state", async () => {
  server.use(http.get("/api/v1/projects/42/analytics/tests", () => HttpResponse.json([])));
  renderTests();
  expect(await screen.findByText(/no tests/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/pages/TestsPage.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement**

`dashboard/src/pages/TestsPage.tsx`:

```tsx
import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { formatDuration, formatPassRate, getTests } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import StatusDot from "../components/StatusDot";

const PAGE = 50;

export default function TestsPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [days, setDays] = useState(30);
  const [sort, setSort] = useState<"failures" | "duration" | "name">("failures");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);

  const query = useQuery({
    queryKey: ["tests", id, days, sort, search, offset],
    queryFn: () => getTests(id, { days, sort, search: search || undefined, limit: PAGE, offset }),
    placeholderData: keepPreviousData,
  });

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    setSearch(searchInput);
    setOffset(0);
  }

  const rows = query.data ?? [];

  return (
    <section>
      <form onSubmit={applyFilters}>
        <FilterBar>
          <label>
            Days
            <select value={days} onChange={(e) => { setDays(Number(e.target.value)); setOffset(0); }}>
              <option value={7}>7</option>
              <option value={30}>30</option>
              <option value={90}>90</option>
            </select>
          </label>
          <label>
            Sort
            <select value={sort} onChange={(e) => { setSort(e.target.value as typeof sort); setOffset(0); }}>
              <option value="failures">Failures</option>
              <option value="duration">Duration</option>
              <option value="name">Name</option>
            </select>
          </label>
          <label>
            Search
            <input value={searchInput} onChange={(e) => setSearchInput(e.target.value)} />
          </label>
          <button type="submit">Apply</button>
        </FilterBar>
      </form>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading tests…</p>}
      {query.data && rows.length === 0 && <p className="muted">No tests in the last {days} days.</p>}

      {rows.length > 0 && (
        <div className="card">
          <table className="data">
            <thead>
              <tr>
                <th>Test</th><th>Runs</th><th>Pass rate</th><th>Failed</th>
                <th>Errored</th><th>Avg duration</th><th>Last status</th><th>Last seen</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.test_key}>
                  <td>
                    <Link to={`../tests/${encodeURIComponent(r.test_key)}`} relative="path">
                      {r.name}
                    </Link>
                    <div className="muted">{r.suite} / {r.class_name}</div>
                  </td>
                  <td>{r.runs}</td>
                  <td>{formatPassRate(r.pass_rate)}</td>
                  <td>{r.failed}</td>
                  <td>{r.errored}</td>
                  <td>{formatDuration(r.avg_duration_ms)}</td>
                  <td><StatusDot status={r.last_status} /></td>
                  <td>{new Date(r.last_seen).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="filters">
            <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
              Previous
            </button>
            <span className="muted">Rows {offset + 1}–{offset + rows.length}</span>
            <button disabled={rows.length < PAGE} onClick={() => setOffset(offset + PAGE)}>
              Next
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Run tests, typecheck, lint**

Run: `npm run test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat(dashboard): per-test statistics table with search, sort and pagination"
```

---

### Task 11: Test history view

**Files:**
- Modify: `dashboard/src/pages/HistoryPage.tsx` (replace placeholder)
- Test: `dashboard/src/pages/HistoryPage.test.tsx`

**Interfaces:**
- Consumes: `getHistory`, `formatPassRate`, `formatDuration`, `StatusDot`, `FilterBar`, `ErrorBanner`. Route param `testKey` arrives URL-encoded; `useParams` decodes it — pass the decoded key to `getHistory` (which re-encodes).

- [ ] **Step 1: Write the failing tests**

`dashboard/src/pages/HistoryPage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens } from "../auth/tokens";
import HistoryPage from "./HistoryPage";

const KEY = "tests/a.py::TestLogin::test_ok";

const history = {
  test_key: KEY, suite: "auth", class_name: "TestLogin", name: "test_ok",
  summary: { runs: 3, passed: 2, failed: 1, errored: 0, skipped: 0, pass_rate: 0.667, avg_duration_ms: 500 },
  executions: [
    { run_id: 9, started_at: "2026-09-30T10:00:00Z", branch: "main", commit_sha: "abcdef1234567890",
      environment: "ci", status: "failed", duration_ms: 480,
      message: "AssertionError: expected 200 got 500\n(very long trace)" },
  ],
};

function renderHistory() {
  setTokens("acc", "ref");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/projects/42/tests/${encodeURIComponent(KEY)}`]}>
        <Routes>
          <Route path="/projects/:projectId/tests/:testKey" element={<HistoryPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("fetches with the encoded key and renders executions", async () => {
  let hit = false;
  server.use(
    http.get(`/api/v1/projects/42/analytics/tests/${encodeURIComponent(KEY)}/history`, () => {
      hit = true;
      return HttpResponse.json(history);
    }),
  );
  renderHistory();
  expect(await screen.findByText("test_ok")).toBeInTheDocument();
  expect(screen.getByText("abcdef1")).toBeInTheDocument(); // short SHA
  expect(hit).toBe(true);
});

test("message is truncated and expandable", async () => {
  server.use(
    http.get(`/api/v1/projects/42/analytics/tests/${encodeURIComponent(KEY)}/history`, () =>
      HttpResponse.json(history),
    ),
  );
  renderHistory();
  await screen.findByText("test_ok");
  expect(screen.queryByText(/very long trace/)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /show full message/i }));
  expect(screen.getByText(/very long trace/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/pages/HistoryPage.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement**

`dashboard/src/pages/HistoryPage.tsx`:

```tsx
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { formatDuration, formatPassRate, getHistory } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import StatusDot from "../components/StatusDot";

function Message({ text }: { text: string | null }) {
  const [open, setOpen] = useState(false);
  if (!text) return <span className="muted">—</span>;
  const firstLine = text.split("\n")[0];
  if (text === firstLine) return <span>{text}</span>;
  return open ? (
    <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{text}</pre>
  ) : (
    <span>
      {firstLine}{" "}
      <button onClick={() => setOpen(true)}>Show full message</button>
    </span>
  );
}

export default function HistoryPage() {
  const { projectId, testKey } = useParams();
  const id = Number(projectId);
  const [days, setDays] = useState(30);
  const [branch, setBranch] = useState("");

  const query = useQuery({
    queryKey: ["history", id, testKey, days, branch],
    queryFn: () => getHistory(id, testKey!, { days, branch: branch || undefined, limit: 100 }),
  });

  const data = query.data;

  return (
    <section>
      <p>
        <Link to=".." relative="path">← All tests</Link>
      </p>
      <FilterBar>
        <label>
          Days
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>7</option>
            <option value={30}>30</option>
            <option value={90}>90</option>
          </select>
        </label>
        <label>
          Branch
          <input value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="all" />
        </label>
      </FilterBar>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading history…</p>}

      {data && (
        <>
          <h2>{data.name}</h2>
          <p className="muted">{data.suite} / {data.class_name}</p>
          <div className="tiles">
            <div className="card">
              <div className="tile-value">{data.summary.runs}</div>
              <div className="tile-label">Executions ({days} days)</div>
            </div>
            <div className="card">
              <div className="tile-value">{formatPassRate(data.summary.pass_rate)}</div>
              <div className="tile-label">Pass rate</div>
            </div>
            <div className="card">
              <div className="tile-value">{formatDuration(data.summary.avg_duration_ms)}</div>
              <div className="tile-label">Avg duration</div>
            </div>
          </div>
          {data.executions.length === 0 ? (
            <p className="muted">No executions in the last {days} days.</p>
          ) : (
            <div className="card">
              <table className="data">
                <thead>
                  <tr>
                    <th>Run</th><th>Started</th><th>Branch</th><th>Commit</th>
                    <th>Environment</th><th>Status</th><th>Duration</th><th>Message</th>
                  </tr>
                </thead>
                <tbody>
                  {data.executions.map((x) => (
                    <tr key={`${x.run_id}-${x.started_at}`}>
                      <td>{x.run_id}</td>
                      <td>{new Date(x.started_at).toLocaleString()}</td>
                      <td>{x.branch ?? "—"}</td>
                      <td>{x.commit_sha ? x.commit_sha.slice(0, 7) : "—"}</td>
                      <td>{x.environment ?? "—"}</td>
                      <td><StatusDot status={x.status} /></td>
                      <td>{formatDuration(x.duration_ms)}</td>
                      <td><Message text={x.message} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Run tests, typecheck, lint**

Run: `npm run test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat(dashboard): test history view with execution list"
```

---

### Task 12: Flaky tests view

**Files:**
- Modify: `dashboard/src/pages/FlakyPage.tsx` (replace placeholder)
- Test: `dashboard/src/pages/FlakyPage.test.tsx`

**Interfaces:**
- Consumes: `getFlaky`, `formatPassRate`, `StatusDot`, `FilterBar`, `ErrorBanner`. Reason labels: `same_commit` → "Confirmed" (flipped on the same commit + environment), `flips` → "Suspected" (status flips over time). Test names link to history like Task 10.

- [ ] **Step 1: Write the failing tests**

`dashboard/src/pages/FlakyPage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setTokens } from "../auth/tokens";
import FlakyPage from "./FlakyPage";

const flaky = [
  {
    test_key: "k1", suite: "auth", class_name: "TestLogin", name: "test_ok",
    reason: "same_commit", commits: [{ commit_sha: "abcdef1234", environment: "ci" }],
    flips: null, flip_rate: null, runs: 12, last_status: "passed", last_seen: "2026-09-30T10:00:00Z",
  },
  {
    test_key: "k2", suite: "cart", class_name: "TestCart", name: "test_add",
    reason: "flips", commits: [], flips: 5, flip_rate: 0.42, runs: 12,
    last_status: "failed", last_seen: "2026-09-30T11:00:00Z",
  },
];

function renderFlaky() {
  setTokens("acc", "ref");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/projects/42/flaky"]}>
        <Routes>
          <Route path="/projects/:projectId/flaky" element={<FlakyPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders confirmed and suspected rows with flip rate", async () => {
  server.use(http.get("/api/v1/projects/42/analytics/flaky", () => HttpResponse.json(flaky)));
  renderFlaky();
  expect(await screen.findByText("Confirmed")).toBeInTheDocument();
  expect(screen.getByText("Suspected")).toBeInTheDocument();
  expect(screen.getByText("42.0%")).toBeInTheDocument();
});

test("controls map to snake_case params", async () => {
  const calls: URLSearchParams[] = [];
  server.use(
    http.get("/api/v1/projects/42/analytics/flaky", ({ request }) => {
      calls.push(new URL(request.url).searchParams);
      return HttpResponse.json([]);
    }),
  );
  renderFlaky();
  await screen.findByText(/no flaky tests/i);
  await userEvent.selectOptions(screen.getByLabelText(/window/i), "30");
  await screen.findByText(/no flaky tests/i);
  const last = calls[calls.length - 1];
  expect(last.get("window_days")).toBe("30");
  expect(last.get("min_runs")).toBe("5");
  expect(last.get("min_flip_rate")).toBe("0.3");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/pages/FlakyPage.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement**

`dashboard/src/pages/FlakyPage.tsx`:

```tsx
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { formatPassRate, getFlaky } from "../api/analytics";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import StatusDot from "../components/StatusDot";

export default function FlakyPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const [windowDays, setWindowDays] = useState(14);
  const [minRuns, setMinRuns] = useState(5);
  const [minFlipRate, setMinFlipRate] = useState(0.3);
  const [branch, setBranch] = useState("");

  const query = useQuery({
    queryKey: ["flaky", id, windowDays, minRuns, minFlipRate, branch],
    queryFn: () => getFlaky(id, { windowDays, minRuns, minFlipRate, branch: branch || undefined }),
  });

  const rows = query.data ?? [];

  return (
    <section>
      <FilterBar>
        <label>
          Window (days)
          <select value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))}>
            <option value={7}>7</option>
            <option value={14}>14</option>
            <option value={30}>30</option>
          </select>
        </label>
        <label>
          Min runs
          <input
            type="number" min={2} max={1000} value={minRuns}
            onChange={(e) => setMinRuns(Number(e.target.value))}
          />
        </label>
        <label>
          Min flip rate
          <input
            type="number" min={0} max={1} step={0.05} value={minFlipRate}
            onChange={(e) => setMinFlipRate(Number(e.target.value))}
          />
        </label>
        <label>
          Branch
          <input value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="all" />
        </label>
      </FilterBar>

      {query.error != null && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}
      {query.isPending && <p className="muted">Loading flaky tests…</p>}
      {query.data && rows.length === 0 && (
        <p className="muted">No flaky tests in the last {windowDays} days. 🎉</p>
      )}

      {rows.length > 0 && (
        <div className="card">
          <table className="data">
            <thead>
              <tr>
                <th>Test</th><th>Reason</th><th>Flips</th><th>Flip rate</th>
                <th>Runs</th><th>Last status</th><th>Commits</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.test_key}>
                  <td>
                    <Link to={`../tests/${encodeURIComponent(r.test_key)}`} relative="path">
                      {r.name}
                    </Link>
                    <div className="muted">{r.suite} / {r.class_name}</div>
                  </td>
                  <td>{r.reason === "same_commit" ? "Confirmed" : "Suspected"}</td>
                  <td>{r.flips ?? "—"}</td>
                  <td>{formatPassRate(r.flip_rate)}</td>
                  <td>{r.runs}</td>
                  <td><StatusDot status={r.last_status} /></td>
                  <td>
                    {r.commits.length === 0 ? (
                      <span className="muted">—</span>
                    ) : (
                      <details>
                        <summary>{r.commits.length} commit(s)</summary>
                        <ul>
                          {r.commits.map((c, i) => (
                            <li key={i}>
                              {c.commit_sha.slice(0, 7)}
                              {c.environment && <span className="muted"> · {c.environment}</span>}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Run tests, typecheck, lint**

Run: `npm run test && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat(dashboard): flaky tests view with detection controls"
```

---

### Task 13: CI job, full-stack verification, docs

**Files:**
- Modify: `.github/workflows/ci.yml` (new `dashboard` job)
- Modify: `TODO.md` (tick Dashboard UI; add follow-ups)
- Create: `dashboard/README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: CI job**

Add to `.github/workflows/ci.yml` beside the other jobs (the `gateway` job needs no change — `docker compose up --build` already builds the dashboard image via the compose file, and the updated smoke script covers it):

```yaml
  dashboard:
    name: Dashboard
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: dashboard
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: dashboard/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Lint
        run: npm run lint

      - name: Typecheck
        run: npm run typecheck

      - name: Tests
        run: npm run test

      - name: Build
        run: npm run build
```

- [ ] **Step 2: Full-stack verification, including a visual check**

```bash
export SECRET_KEY=dev-secret INTERNAL_API_PASSWORD=dev-internal
docker compose up -d --build --wait gateway dashboard
bash scripts/smoke_gateway.sh
```

Expected: all checks ok. Then open `https://localhost:8443/` in a browser (or drive it with the available browser tooling): register/login a user, create an org + project + API key through the API, upload a run with the collector or curl, and eyeball all four views — chart renders without label collisions, dark mode follows the OS setting, tables align. Fix what looks broken before committing. Tear down with `docker compose down -v`.

- [ ] **Step 3: Docs**

`dashboard/README.md`:

```markdown
# QA Vision Dashboard

React + Vite + TypeScript SPA for the analytics API. Served as static files
by nginx behind the platform gateway (`location /`), so the app and the API
share one origin.

## Develop

    cd dashboard
    npm install
    npm run dev      # Vite dev server; /api/* proxied to https://localhost:8443

Run the stack first (`docker compose up -d --build --wait gateway`) so the
API answers.

## Test / check

    npm run test       # Vitest + Testing Library + MSW
    npm run typecheck  # tsc --noEmit
    npm run lint       # eslint
    npm run build      # production build to dist/

## Auth model

Access token in memory; refresh token in sessionStorage (per tab). On 401 the
client refreshes once (rotation-aware) and retries; a failed refresh returns
to /login.
```

In `TODO.md` under "Analytics API (Phase 3, step 1)": change `- [ ] Dashboard UI` to `- [x] Dashboard UI — login, project picker, trends, tests, history, flaky (dashboard/)` and add below it:

```markdown
### Dashboard follow-ups
- [ ] SSO sign-in buttons (Google, Microsooft) in the login page
- [ ] Refresh token in an httpOnly cookie (needs auth-service support)
- [ ] Mute / acknowledge flaky tests (needs a write API)
- [ ] CSV export buttons on the tests and flaky views
- [ ] Branch comparison view
```

(Fix the typo: "Microsoft".)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml TODO.md dashboard/README.md
git commit -m "ci(dashboard): node job; docs and TODO updates for the dashboard MVP"
```

---

## Final verification (whole branch)

- [ ] `cd platforms/organization-service && python -m pytest tests/ -q` — green
- [ ] `cd dashboard && npm run lint && npm run typecheck && npm run test && npm run build` — green
- [ ] Full stack: `docker compose up -d --build --wait gateway dashboard && bash scripts/smoke_gateway.sh` — all ok; manual visual pass over the four views
- [ ] `docker compose down -v`
- [ ] Request code review (superpowers:requesting-code-review) before the PR
