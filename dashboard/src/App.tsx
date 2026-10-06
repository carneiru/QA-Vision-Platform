import { Suspense, lazy, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { focusContent, pageTitle, useFocusOnNavigate } from "./routeFocus";
import { bootstrapSession, setOnAuthFailure } from "./api/http";
import AppShell from "./components/AppShell";
import RequireAuth from "./components/RequireAuth";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import PickerPage from "./pages/PickerPage";
import ProjectLayout from "./pages/ProjectLayout";
import SecurityPage from "./pages/SecurityPage";
import TestsPage from "./pages/TestsPage";
import HistoryPage from "./pages/HistoryPage";
import FlakyPage from "./pages/FlakyPage";
import RunsPage from "./pages/RunsPage";
import ComparePage from "./pages/ComparePage";
import CaseEditorPage from "./pages/CaseEditorPage";
import CasesPage from "./pages/CasesPage";
import SuiteDetailPage from "./pages/SuiteDetailPage";
import SuitesPage from "./pages/SuitesPage";
import RunDetailPage from "./pages/RunDetailPage";
import OrganizationPage from "./pages/OrganizationPage";
import ProjectSettingsPage from "./pages/ProjectSettingsPage";
import OverviewPage from "./pages/OverviewPage";
import ReportPage from "./pages/ReportPage";
import InvitationAcceptPage from "./pages/InvitationAcceptPage";

// Recharts dominates the bundle; the chart-bearing views load on demand.
const TrendsPage = lazy(() => import("./pages/TrendsPage"));
const BranchesPage = lazy(() => import("./pages/BranchesPage"));

// Project views set their own title (view + project name) in ProjectLayout
const TITLES: [string, string][] = [
  ["/login", "Sign in"],
  ["/register", "Create account"],
  ["/verify-email", "Verify email"],
  ["/forgot-password", "Reset password"],
  ["/reset-password", "Choose a new password"],
  ["/account/security", "Security"],
  ["/organizations/", "Organization"],
  ["/invitations/", "Invitation"],
];

function titleFor(pathname: string): string {
  const match = TITLES.find(([prefix]) => pathname.startsWith(prefix));
  return pageTitle(match ? match[1] : "Projects");
}

/** Sign-in pages have no navigation: the whole page is the main content. */
function PublicMain() {
  return (
    <main id="main" tabIndex={-1}>
      <Outlet />
    </main>
  );
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
      <Routes>
        <Route element={<PublicMain />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
        </Route>
        <Route element={<RequireAuth><AppShell /></RequireAuth>}>
          <Route path="/" element={<PickerPage />} />
          <Route path="/account/security" element={<SecurityPage />} />
          <Route path="/organizations/:orgId" element={<OrganizationPage />} />
          <Route path="/invitations/:token" element={<InvitationAcceptPage />} />
          <Route path="/projects/:projectId" element={<ProjectLayout />}>
            <Route index element={<Navigate to="overview" replace />} />
            <Route path="overview" element={<OverviewPage />} />
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
            <Route path="runs/:runId/compare/:baseId" element={<ComparePage />} />
            <Route path="report" element={<ReportPage />} />
            <Route path="cases" element={<CasesPage />} />
            <Route path="cases/new" element={<CaseEditorPage />} />
            <Route path="cases/:caseNumber" element={<CaseEditorPage />} />
            <Route path="suites" element={<SuitesPage />} />
            <Route path="suites/:suiteId" element={<SuiteDetailPage />} />
            <Route path="settings" element={<ProjectSettingsPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
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
