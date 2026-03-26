import { Navigate, Outlet, createBrowserRouter } from "react-router-dom";
import { AppShell } from "@/components/layout/app-shell";
import { useAuthStore } from "@/store/auth-store";
import type { Role } from "@/types/domain";
import { HomePage } from "@/pages/home-page";
import { LoginPage } from "@/pages/auth/login-page";
import { RegisterPage } from "@/pages/auth/register-page";
import { ApplicantDashboardPage } from "@/pages/applicant/dashboard-page";
import { ApplicantProfilePage } from "@/pages/applicant/profile-page";
import { ProgramsPage } from "@/pages/applicant/programs-page";
import { ProgramDetailPage } from "@/pages/applicant/program-detail-page";
import { MatchesPage } from "@/pages/applicant/matches-page";
import { NotificationsPage } from "@/pages/applicant/notifications-page";
import { AdminDashboardPage } from "@/pages/admin/admin-dashboard-page";
import { ProgramReviewPage } from "@/pages/admin/program-review-page";
import { ScraperRunsPage } from "@/pages/admin/scraper-runs-page";
import { MatchingRulesPage } from "@/pages/admin/matching-rules-page";
import { InterventionsPage } from "@/pages/admin/interventions-page";
import { NotFoundPage } from "@/pages/not-found-page";

function ProtectedRoute({ role }: { role?: Role }) {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated || !user) {
    return <Navigate to="/auth/login" replace />;
  }

  if (role && user.role !== role) {
    return <Navigate to={user.role === "admin" ? "/admin/dashboard" : "/app/dashboard"} replace />;
  }

  return <Outlet />;
}

export const router = createBrowserRouter([
  { path: "/", element: <HomePage /> },
  { path: "/auth/login", element: <LoginPage /> },
  { path: "/auth/register", element: <RegisterPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          {
            element: <ProtectedRoute role="applicant" />,
            children: [
              { path: "/app/dashboard", element: <ApplicantDashboardPage /> },
              { path: "/app/profile", element: <ApplicantProfilePage /> },
              { path: "/app/programs", element: <ProgramsPage /> },
              { path: "/app/programs/:programId", element: <ProgramDetailPage /> },
              { path: "/app/matches", element: <MatchesPage /> },
              { path: "/app/notifications", element: <NotificationsPage /> }
            ]
          },
          {
            element: <ProtectedRoute role="admin" />,
            children: [
              { path: "/admin/dashboard", element: <AdminDashboardPage /> },
              { path: "/admin/programs", element: <ProgramReviewPage /> },
              { path: "/admin/programs/:programId", element: <ProgramDetailPage /> },
              { path: "/admin/scraper-runs", element: <ScraperRunsPage /> },
              { path: "/admin/matching-rules", element: <MatchingRulesPage /> },
              { path: "/admin/interventions", element: <InterventionsPage /> }
            ]
          }
        ]
      }
    ]
  },
  { path: "*", element: <NotFoundPage /> }
]);
