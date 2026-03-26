import { useQuery } from "@tanstack/react-query";
import { StatCard } from "@/components/shared/stat-card";
import { SectionHeader } from "@/components/shared/section-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/services/api/client";

export function ApplicantDashboardPage() {
  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: apiClient.getCurrentUserProfile
  });

  const { data: matches } = useQuery({
    queryKey: ["matches"],
    queryFn: () => apiClient.getMatchesByUser("user_001")
  });

  return (
    <div>
      <SectionHeader
        title="Applicant Dashboard"
        description="See your profile readiness, latest matches, and next actions in one place."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          label="Profile completeness"
          value={`${profile?.profileCompleteness ?? 0}%`}
          caption="Aim for 90%+ to improve match quality"
        />
        <StatCard
          label="Qualified opportunities"
          value={String(matches?.length ?? 0)}
          caption="Updated from the latest matching run"
        />
        <StatCard label="Deadline alerts" value="2" caption="Upcoming in the next 14 days" />
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Recent Match Signals</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {matches?.map((match) => (
            <div key={match.id} className="rounded-lg border p-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-semibold">Program ID: {match.programId}</p>
                <Badge variant={match.status === "high_fit" ? "success" : "secondary"}>
                  {match.status.replace("_", " ")}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">Match score: {match.score}/100</p>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-sm">
                {match.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
