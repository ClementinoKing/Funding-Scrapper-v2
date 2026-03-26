import type { Role } from "@/types/domain";

export interface NavItem {
  label: string;
  path: string;
}

export const navByRole: Record<Role, NavItem[]> = {
  applicant: [
    { label: "Overview", path: "/app/dashboard" },
    { label: "My Profile", path: "/app/profile" },
    { label: "Programs", path: "/app/programs" },
    { label: "My Matches", path: "/app/matches" },
    { label: "Notifications", path: "/app/notifications" }
  ],
  admin: [
    { label: "Admin Home", path: "/admin/dashboard" },
    { label: "Program Review", path: "/admin/programs" },
    { label: "Scraper Runs", path: "/admin/scraper-runs" },
    { label: "Matching Rules", path: "/admin/matching-rules" },
    { label: "Interventions", path: "/admin/interventions" }
  ]
};
