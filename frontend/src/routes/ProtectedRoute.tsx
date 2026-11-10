import { Navigate, Outlet, useLocation } from "react-router-dom";
import { PageSpinner } from "@/components/ui/feedback";
import { useAuth } from "@/features/auth/AuthContext";
import type { Role } from "@/types";

interface Props {
  roles?: Role[];
  /** Where to send a signed-in user whose role isn't allowed. Must not itself be protected. */
  fallback?: string;
}

export default function ProtectedRoute({ roles, fallback = "/" }: Props) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <PageSpinner />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to={fallback} replace />;
  return <Outlet />;
}
