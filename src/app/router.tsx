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
import { FinalProgrammesPage } from "@/pages/admin/final-programmes-page";
import { ProgramReviewPage } from "@/pages/admin/program-review-page";
import { WebsitesPage } from "@/pages/admin/websites-page";
import { WebsiteDetailPage } from "@/pages/admin/website-detail-page";
import { ScraperRunsPage } from "@/pages/admin/scraper-runs-page";
import { ScrapeRunDetailPage } from "@/pages/admin/scrape-run-detail-page";
import { MatchingRulesPage } from "@/pages/admin/matching-rules-page";
import { InterventionsPage } from "@/pages/admin/interventions-page";
import { ChangeLogPage } from "@/pages/admin/change-log-page";
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
              { path: "/admin/final-programmes", element: <FinalProgrammesPage /> },
              { path: "/admin/programs", element: <ProgramReviewPage /> },
              { path: "/admin/programs/:programId", element: <ProgramDetailPage /> },
              { path: "/admin/websites", element: <WebsitesPage /> },
              { path: "/admin/websites/:siteKey", element: <WebsiteDetailPage /> },
              {
                path: "/admin/scraper-runs",
                children: [
                  { index: true, element: <ScraperRunsPage /> },
                  { path: ":runId", element: <ScrapeRunDetailPage /> }
                ]
              },
              { path: "/admin/matching-rules", element: <MatchingRulesPage /> },
              { path: "/admin/change-log", element: <ChangeLogPage /> },
              { path: "/admin/interventions", element: <InterventionsPage /> }
            ]
          }
        ]
      }
    ]
  },
  { path: "*", element: <NotFoundPage /> }
]);
