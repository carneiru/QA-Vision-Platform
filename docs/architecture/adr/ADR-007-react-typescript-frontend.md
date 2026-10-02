# ADR-007: Select React 5+ for Frontend Applications

- Status: Proposed (TARGET architecture; reclassified 2026-10-02 — adopt only when the Blueprint's Implementation Status trigger fires; nothing here is deployed)
- Date: 2024-03-05
- Version: 1.0
- Authors: Architecture Team
- Decision Owner: Chief Architect
- Supersedes: None
- Superseded By: None

---

# Context

## Business Problem
The QEOS platform requires a modern, maintainable, and performant frontend framework to build user‑facing applications across multiple domains (Platform, Execution, QIP, Automation, Collaboration, Administration, Marketplace, Integrations). The chosen framework must support rapid development, a rich ecosystem of UI components, strong community backing, and seamless integration with our existing backend services (Go, Python, Node.js).

## Technical Problem
Evaluating frontend frameworks involves assessing factors such as component model, state management, tooling, performance, bundle size, learning curve, ecosystem maturity, and long‑term viability. The framework must enable reusable UI components, efficient rendering, and easy testing while fitting into our containerized, micro‑service architecture.

## Architectural Drivers
- Component‑based architecture for reusable UI elements
- Strong community and third‑party library support
- Mature tooling for bundling, testing, and debugging (Webpack, Vite, Jest, Storybook)
- Server‑side rendering (SSR) and static site generation (SSG) capabilities for SEO and performance
- Excellent TypeScript support for type‑safe frontend development
- Ability to adopt incremental migration from legacy jQuery‑based pages
- Support for micro‑frontend architectures and module federation
- Accessibility (a11y) and internationalization (i18n) out of the box or via mature plugins
- Performance optimizations (code‑splitting, lazy loading, suspense)

## Constraints
- Must integrate with existing API gateway and authentication services (OAuth2/JWT)
- Must be deployable in containerized environments (Docker/Kubernetes)
- Must interoperate with services written in Go, Python, and Node.js via REST/GraphQL
- Must comply with enterprise security standards (CSP, XSS protection, secure headers)
- Team familiarity or willingness to adopt the framework
- Licensing must be permissive for commercial use
- Bundle size budgets to meet performance targets (TTI < 3s on 3G)

## Assumptions
- Organization will invest in React/TypeScript training for frontend engineers
- Existing CI/CD pipelines can accommodate Node.js‑based build processes
- The React ecosystem provides sufficient UI component libraries (MUI, Ant Design, Chakra UI)
- Long‑term support for React 18+ is guaranteed by Meta and the open‑source community
- Backend APIs will adhere to RESTful or GraphQL contracts consumable by frontend clients

## Architecture Principles Addressed
- AP-001: Business Capability Alignment - Systems should be organized around business capabilities
- AP-005: Ubiquitous Language - Common language should be shared between domain experts and developers
- AP-006: Asynchronous Communication - Use async patterns for better scalability and resilience
- AP-009: Scalability - Systems should handle increased load through horizontal scaling
- AP-010: Auditability - User interactions should be traceable for compliance and analysis
- AP-011: Performance - Systems should be responsive and performant under expected loads

## Quality Attributes Involved
- Developer productivity
- Maintainability
- Performance (runtime and load time)
- Scalability (team and application)
- Testability
- Accessibility
- Internationalization readiness

---

# Decision
Select React 5+ (specifically React 18.x with concurrent features) as the primary frontend library for building SPAs and server‑side rendered applications in the QEOS platform, paired with TypeScript for static typing.

## Scope
This decision applies to all user‑facing web applications within the QEOS platform, including dashboards, administration portals, customer‐facing portals, and any internal tools that require a rich interactive interface.

## Affected Domains
All domains: Platform, Execution, Quality Intelligence Platform (QIP), Automation, Collaboration, Administration, Marketplace, and Integrations

## Implementation Boundaries
- Use React 18+ (or later) with concurrent mode where beneficial
- Adopt TypeScript 4.9+ for all new components and gradually migrate existing JavaScript files
- State management via React Context for local state and Redux Toolkit or Zustand for global/shared state
- Routing with React Router v6+
- Styling approach: CSS Modules or Styled Components; avoid inline styles where possible
- Data fetching: React Query (TanStack Query) or SWR for caching, background updates, and mutation handling
- Form handling: React Hook Form with Yup/Zod validation
- UI component library: Material‑UI (MUI) v5 or Ant Design for consistency and accessibility
- Testing: Jest + React Testing Library for unit/integration tests; Cypress for end‑to‑end scenarios
- Build tooling: Vite (default) or Webpack 5 with Module Federation for micro‑frontends
  - Linting/formatting: ESLint with @typescript-eslint and Prettier
- Code splitting and lazy loading via React.lazy and Suspense
- Server‑side rendering (SSR) using Next.js 13+ (App Router) for SEO‑critical pages, otherwise pure SPA
- Environment variables handled via .env files and validated with zod or similar
- Dockerize frontend builds using multi‑stage Node.js → nginx (or Caddy) for efficient production images
- Deploy to Kubernetes via Deployments/Services; expose via Ingress with TLS termination
- Feature flags via LaunchDarkly or similar for gradual rollouts
- Monitoring: Web Vitals (CLS, LCP, FID) reported to observability stack (Grafana/Prometheus)
- Error tracking via Sentry.io with source maps
- Accessibility testing using axe‑core in CI
- Internationalization using react‑i18next or formatjs

---

# Alternatives Considered

## Vue 3.x
### Pros
- Gentle learning curve, especially for developers from HTML/CSS background
- Excellent documentation and official tooling (Vite, Vue CLI)
- Reactive system based on proxies (fine‑grained updates)
- Single‑file components (SFC) keep template, logic, and styles together
- Strong TypeScript support
- Official state management (Pinia) and routing (Vue Router)

### Cons
- Smaller ecosystem compared to React (fewer third‑party component libraries)
- Less traction in enterprise‑grade large‑scale applications
- Community and hiring pool smaller than React
- Vue 3’s Composition API, while powerful, can be unfamiliar to teams accustomed to class‑based or Hooks patterns

### Decision
Not selected

### Reason
While Vue is a strong contender, React’s larger ecosystem, mature tooling for server‑side rendering (Next.js), and broader industry adoption make it a safer long‑term bet for the QEOS platform’s diverse frontend needs.

## Angular 15+
### Pros
- Opinionated, full‑featured framework (CLI, router, forms, HTTP client, animations)
- Strong TypeScript integration from the ground up
- Built‑in dependency injection and RxJS for reactive programming
- Excellent tooling (Angular CLI, Augury) and long‑term LTS support from Google
- Ahead‑of‑time (AOT) compilation and Ivy renderer for smaller bundles

### Cons
- Steeper learning curve due to opinionated architecture and extensive API surface
- Larger bundle size compared to React/Vue unless aggressive lazy loading is applied
- Less flexibility in choosing alternative state‑management or routing libraries
- Migration from AngularJS (if any) would be a major effort
- Template syntax can be verbose for simple UI logic

### Decision
Not selected

### Reason
Angular’s opinionated nature and higher initial complexity conflict with our goal of enabling rapid iteration and gradual adoption across multiple teams; React offers a more incremental adoption path and a richer ecosystem of UI libraries.

## Svelte / SvelteKit
### Pros
- Compiler‑based approach yields minimal runtime overhead and tiny bundle sizes
- Reactive declarations simplify state management
- No virtual DOM, leading to faster updates
- SvelteKit provides file‑based routing, server‑side rendering, and adapters for various platforms
- Growing enthusiasm and positive developer experience feedback

### Cons
- Nascent ecosystem; fewer mature UI component libraries compared to React
- Limited tooling for large‑scale enterprise applications (e.g., advanced debugging, profiling)
- Smaller community and hiring pool
- Less proven track record in mission‑critical, high‑traffic financial or healthcare applications

### Decision
Not selected

### Reason
Although Svelte offers impressive performance, its immature ecosystem and limited enterprise adoption pose risks for long‑term maintenance and hiring; React provides a proven, battle‑tested foundation for our needs.

## Lit (Web Components)
### Pros
- Framework‑agnostic, enables creation of reusable custom elements
- Lightweight and fast, leverages native shadow DOM
- Good for design‑system distribution across multiple frameworks

### Cons
- Requires a shift in mindset for teams used to component‑based frameworks
- Lack of built‑in routing, state‑management, and CLI tooling (needs additional libraries)
- SSR support is less mature than Next.js/Nuxt
- Not ideal for building complex SPAs with nested views and dynamic data fetching

### Decision
Not selected

### Reason
While Lit is excellent for sharing UI primitives, it does not provide the full‑featured SPA solution required for most of our applications; we will still use Lit internally for design‑system pieces where appropriate.

---

# Consequences

## Positive
- Access to the largest and most mature frontend ecosystem (libraries, tools, talent)
- Component‑based architecture encourages reuse and maintainability
- Concurrent mode (React 18) improves responsiveness for interruptible rendering
- Rich server‑side rendering solutions (Next.js) enable SEO and fast initial loads
- Strong TypeScript integration catches bugs at compile time
- Huge pool of skilled developers simplifies hiring and onboarding
- Mature testing libraries (Jest, RTL, Cypress) support high confidence releases
- Effective code‑splitting and lazy loading reduce initial bundle size
- Vibrant open‑source community ensures rapid bug fixes and feature updates

## Negative
- Frequent release cycle can introduce breaking changes (mitigated by LTS versions and codemods)
- Virtual DOM overhead, though minimal for most UI workloads
- Boilerplate for store setup (e.g., Redux) can be verbose (addressed by RTK or Zustand)
- JSK syntax may be unfamiliar to designers coming from HTML‑only backgrounds (mitigated by training)
- Bundle size can grow if not carefully managed (addressed via code‑splitting, tree‑shaking)
- Requires discipline to avoid “wrapper component hell” and deep prop drilling (mitigated by context, custom hooks, or state‑management libraries)

---

# Implementation

## Affected Applications
- Platform Dashboard (internal ops view)
- Execution Console (job monitoring and control)
- QIP Insights Portal (AI/ML model visualisation)
- Automation Builder (workflow designer)
- Collaboration Hub (team communication & docs)
- Admin Console (user/role/tenant management)
- Marketplace Storefront (buyer/seller UI)
- Integration Studio (API & event flow designer)

## Affected Domains
All domains: Platform, Execution, Quality Intelligence Platform (QIP), Automation, Collaboration, Administration, Marketplace, Integrations

## Deployment Guidelines
- Source hosted in monorepo (Nx or Turborepo) or multi‑repo depending on team ownership
- CI pipeline: lint → type‑check → unit-test → build → security scan (npm audit, snyk) → container image push
- Dockerfile:
  ```dockerfile
  FROM node:20-alpine AS builder
  WORKDIR /app
  COPY package*.json ./
  RUN npm ci
  COPY . .
  RUN npm run build   # generates optimized static assets
  FROM nginx:alpine
  COPY --from=builder /app/dist /usr/share/nginx/html
  COPY nginx.conf /etc/nginx/conf.d/default.conf
  EXPOSE 80
  CMD ["nginx", "-g", "daemon off;"]
  ```
- Non‑root user (node) in builder stage; nginx runs as unprivileged user in final image
- Kubernetes manifests include: Deployment, Service, HorizontalPodAutoscaler (CPU‑based), PodDisruptionBudget, Ingress (TLS via cert‑manager)
- Environment-specific configs via ConfigMaps; secrets (API keys, auth tokens) via SealedSecrets or Vault
- Feature flags managed through LaunchDash (or open‑source Unleash) service
- Telemetry:
  - Web‑Vitals sent to Prometheus via node‑exporter sidecar or via Grafana Agent
  - Errors reported to Sentry with source‑map upload step in CI
  - Logs forwarded to Loki via Promtail sidecar
- Accessibility:
  - Automated axe‑core scans in PR workflow
  - Manual screen‑reader testing for critical flows
- Internationalization:
  - JSON message files per locale, loaded via react‑i18next init
  - Language switcher persisted in user profile and localStorage

---

# Risks

| Risk | Mitigation |
|------|------------|
| Version churn breaking existing code | Adopt LTS release line (React 18.x); use automated codemods (react‑codemod) for upgrades; maintain a comprehensive test suite |
| Bundle size bloat affecting load times | Enforce budget via Webpack Bundle Analyzer; code‑split routes and lazy‑load heavy libraries; monitor via Lighthouse CI |
| State‑management complexity leading to bugs | Standardise on Redux Toolkit (RTK) or Zustand; provide team‑wide guidelines and code‑review checklists |
| Learning curve slowing initial delivery | Invest in internal workshops, pair‑programming, and curated learning paths (epic‑react, react.dev) |
| Incompatibile third‑party libraries | Vet dependencies for maintenance status, license compatibility, and peer‑reviewed usage; prefer well‑known packages (MUI, Formik, React Query) |
| Server‑side rendering hydration mismatches | Follow React SSR guidelines; use `suppressHydrationWarning` sparingly; test with React 18’s strict mode |
| Inefficient re‑renders degrading UI responsiveness | Leverage React.memo, useMemo, useCallback; employ React Profilaller in dev builds; educate team on render‑cycle fundamentals |
| Security issues (XSS, CSRF) | Rely on React’s built‑in escaping; enforce CSP headers; sanitize any user‑generated HTML via DOMPurify; validate/authenticate all API calls |
| Accessibility regressions | Integrate axe‑core into CI; conduct quarterly manual audits with assistive technologies |
| Talent shortage for senior React specialists | Grow talent internally via mentorship; consider contractor Augment for specialized initiatives; maintain interview bar focused on fundamentals |

---

# Related Decisions
- ADR-001: Adopt Domain‑Driven Design
- ADR-002: Adopt Event‑Driven Architecture
- ADR-003: Select Kubernetes as Container Orchestrator
- ADR-004: Select Apache Kafka as Event Backbone
- ADR-005: Select Go for Core Infrastructure Services
- ADR-006: Select Python for AI/ML Services
- ADR-008: Select PostgreSQL as Primary Relational Database
- ADR-009: Select Neo4j for Knowledge Graph Storage
- ADR-010: Select Qdrant for Vector Database
- ADR-017: Bounded Context Map and Context Mapping
- ADR-018: Event Sourcing and CQRS Patterns
- ADR-019: Dead Letter Queue Handling
- ADR-020: Service Mesh Adoption

---

# Change Log
| Date | Version | Description |
|------|---------|-------------|
| 2024-03-05 | 1.0 | Initial version |

---

# References
- React Official Documentation – https://react.dev
- Concurrent Mode – https://react.dev/reference/react/useTransition
- React 18 Upgrade Guide – https://reactjs.org/blog/2022/03/29/react-v18.html
- TypeScript – https://www.typescriptlang.org
- Vite – https://vitejs.dev
- Next.js – https://nextjs.org
- React Router – https://reactrouter.com
- Redux Toolkit – https://redux-toolkit.js.org
- Zustand – https://zustand-demo.pmndrs.com
- React Query (TanStack Query) – https://tanstack.com/query/v4
- React Hook Form – https://react-hook-form.com
- Material‑UI (MUI) – https://mui.com
- Ant Design – https://ant.design
- Styled Components – https://styled-components.com
- CSS Modules – https://github.com/css-modules/css-modules
- ESLint – https://eslint.org
- Prettier – https://prettier.io
- Cypress – https://www.cypress.io
- Jest – https://jestjs.io
- React Testing Library – https://testing-library.com/docs/react-testing-library/intro
- Sentry – https://sentry.io
- Grafana Loki – https://grafana.com/oss/loki/
- Prometheus – https://prometheus.io
- Web Vitals – https://web.dev/vitals/
- Lighthouse CI – https://github.com/GoogleChrome/lighthouse-ci
- axe‑core – https://www.deque.com/axe/
- react‑i18next – https://react.i18next.com
- formatjs – https://formatjs.io
- LaunchDarkly – https://launchdarkly.com
- Unleash – https://getunleash.io
- Docker – https://www.docker.com
- Nginx – https://nginx.org
- Helm – https://helm.sh
- Kustomize – https://kustomize.io
- Argo CD – https://argoproj.github.io/cd
- Flux CD – https://fluxcd.io
- CNCF Landscape – https://landscape.cncf.io

---

# Review
Biennial frontend technology stack review or when evaluating alternative frontend frameworks for new or refactored user‑facing applications