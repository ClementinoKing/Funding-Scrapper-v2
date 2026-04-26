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
    { label: "Final Programmes", path: "/admin/final-programmes" },
    { label: "Program Review", path: "/admin/programs" },
    { label: "Websites", path: "/admin/websites" },
    { label: "Scraper Runs", path: "/admin/scraper-runs" },
    { label: "Change Log", path: "/admin/change-log" },
    { label: "Matching Rules", path: "/admin/matching-rules" },
    { label: "AI Rules", path: "/admin/ai-rules" },
    { label: "Interventions", path: "/admin/interventions" }
  ]
};
