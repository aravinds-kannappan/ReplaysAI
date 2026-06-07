import { useAuth } from "@clerk/clerk-react";
import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useCurrentUser } from "../hooks/useUser";

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  const location = useLocation();
  const { data: user, isLoading } = useCurrentUser();

  if (!isLoaded) {
    return <div className="page-center">Loading…</div>;
  }

  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />;
  }

  if (location.pathname !== "/onboarding") {
    const localOnboarded = window.localStorage.getItem("replaysai:onboarded") === "true";
    if (isLoading) return <div className="page-center">Loading your team graph...</div>;
    if (!localOnboarded && !user?.onboarded) {
      return <Navigate to="/onboarding" replace state={{ from: location.pathname }} />;
    }
  }

  return <>{children}</>;
}
