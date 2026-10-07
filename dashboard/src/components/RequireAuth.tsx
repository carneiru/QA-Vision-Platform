import { Navigate, useLocation } from "react-router-dom";
import { isAuthenticated } from "../auth/tokens";
import { loginPath } from "../auth/redirect";

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!isAuthenticated()) return <Navigate to={loginPath(location)} replace />;
  return <>{children}</>;
}
