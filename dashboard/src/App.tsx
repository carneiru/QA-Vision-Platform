import { Suspense, lazy, useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { setOnAuthFailure } from "./api/http";
import RequireAuth from "./components/RequireAuth";
import LoginPage from "./pages/LoginPage";
import PickerPage from "./pages/PickerPage";
import ProjectLayout from "./pages/ProjectLayout";
import TestsPage from "./pages/TestsPage";
import HistoryPage from "./pages/HistoryPage";
import FlakyPage from "./pages/FlakyPage";
import RunsPage from "./pages/RunsPage";
import RunDetailPage from "./pages/RunDetailPage";

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
