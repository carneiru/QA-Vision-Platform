import { Suspense, lazy, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { bootstrapSession, setOnAuthFailure } from "./api/http";
import RequireAuth from "./components/RequireAuth";
import LoginPage from "./pages/LoginPage";
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

export function AppRoutes() {
  const navigate = useNavigate();
  useEffect(() => {
    setOnAuthFailure(() => navigate("/login", { replace: true }));
  }, [navigate]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
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
