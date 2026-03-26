import { useQuery } from "@tanstack/react-query";
import { SectionHeader } from "@/components/shared/section-header";
import { StatCard } from "@/components/shared/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/services/api/client";

export function AdminDashboardPage() {
  const { data: runs = [] } = useQuery({
    queryKey: ["scrape-runs"],
    queryFn: apiClient.getScrapeRuns
  });

  const failedCount = runs.filter((run) => run.status === "failed" || run.status === "partial").length;

  return (
    <div>
      <SectionHeader
        title="Admin Dashboard"
        description="Monitor scraper health, content review queues, and matching quality metrics."
      />
      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Daily scrape runs" value={String(runs.length)} caption="Executed by scheduler" />
        <StatCard label="Attention required" value={String(failedCount)} caption="Partial or failed sources" />
        <StatCard label="Pending approvals" value="6" caption="Scraped records awaiting review" />
        <StatCard label="Manual interventions" value="3" caption="Unmatched high-potential applicants" />
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Daily operations checklist</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          1) Review low-confidence scrape outputs. 2) Approve or reject updated opportunity records. 3) Validate manual-review matches and trigger outreach notifications.
        </CardContent>
      </Card>
    </div>
  );
}
