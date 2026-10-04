import { Suspense, lazy, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { focusContent, pageTitle, useFocusOnNavigate } from "./routeFocus";
import { bootstrapSession, setOnAuthFailure } from "./api/http";
import RequireAuth from "./components/RequireAuth";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";
import PickerPage from "./pages/PickerPage";
import ProjectLayout from "./pages/ProjectLayout";
import SecurityPage from "./pages/SecurityPage";
import TestsPage from "./pages/TestsPage";
import HistoryPage from "./pages/HistoryPage";
import FlakyPage from "./pages/FlakyPage";
import RunsPage from "./pages/RunsPage";
import RunDetailPage from "./pages/RunDetailPage";
import OrganizationPage from "./pages/OrganizationPage";
import ProjectSettingsPage from "./pages/ProjectSettingsPage";
import InvitationAcceptPage from "./pages/InvitationAcceptPage";

// Recharts dominates the bundle; the chart-bearing views load on demand.
const TrendsPage = lazy(() => import("./pages/TrendsPage"));
const BranchesPage = lazy(() => import("./pages/BranchesPage"));

// Project views set their own title (view + project name) in ProjectLayout
const TITLES: [string, string][] = [
  ["/login", "Sign in"],
  ["/register", "Create account"],
  ["/verify-email", "Verify email"],
  ["/account/security", "Security"],
  ["/organizations/", "Organization"],
  ["/invitations/", "Invitation"],
];

function titleFor(pathname: string): string {
  const match = TITLES.find(([prefix]) => pathname.startsWith(prefix));
  return pageTitle(match ? match[1] : "Projects");
}

const outsideProjects = (pathname: string) => !pathname.startsWith("/projects/");

export function AppRoutes() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  useEffect(() => {
    setOnAuthFailure(() => navigate("/login", { replace: true }));
  }, [navigate]);
  useEffect(() => {
    if (outsideProjects(pathname)) document.title = titleFor(pathname);
  }, [pathname]);
  useFocusOnNavigate();

  return (
    <>
      <a
        className="skip-link"
        href="#main"
        onClick={(e) => {
          e.preventDefault();
          focusContent();
        }}
      >
        Skip to content
      </a>
      <main id="main" tabIndex={-1}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/" element={<RequireAuth><PickerPage /></RequireAuth>} />
          <Route path="/account/security" element={<RequireAuth><SecurityPage /></RequireAuth>} />
          <Route path="/organizations/:orgId" element={<RequireAuth><OrganizationPage /></RequireAuth>} />
          <Route path="/invitations/:token" element={<RequireAuth><InvitationAcceptPage /></RequireAuth>} />
          <Route path="/projects/:projectId" element={<RequireAuth><ProjectLayout /></RequireAuth>}>
            <Route index element={<Navigate to="trends" replace />} />
            <Route
              path="trends"
              element={
                <Suspense fallback={<p className="muted">Loading trends…</p>}>
                  <TrendsPage />
                </Suspense>
              }
            />
            <Route path="tests" element={<TestsPage />} />
            <Route path="tests/:testKey" element={<HistoryPage />} />
            <Route path="flaky" element={<FlakyPage />} />
            <Route
              path="branches"
              element={
                <Suspense fallback={<p className="muted">Loading branches…</p>}>
                  <BranchesPage />
                </Suspense>
              }
            />
            <Route path="runs" element={<RunsPage />} />
            <Route path="runs/:runId" element={<RunDetailPage />} />
            <Route path="settings" element={<ProjectSettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
}

export default function App() {
  // Try the httpOnly-cookie session before routing, so a page reload does not
  // bounce a logged-in user to /login.
  const [booted, setBooted] = useState(false);
  useEffect(() => {
    bootstrapSession().finally(() => setBooted(true));
  }, []);

  if (!booted) return <p className="muted page">Loading…</p>;

  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
