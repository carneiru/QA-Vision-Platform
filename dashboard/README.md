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
to /login. A 401 with no stored refresh token (a failed login) is surfaced
as the API's own error detail.
