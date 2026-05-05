import { StatCard } from "@/components/shared/stat-card";
import { SectionHeader } from "@/components/shared/section-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useProfile } from "@/hooks/use-profile";
import { getBusinessMatches } from "@/lib/triggerMatching";
import { UserProfileView } from "@/types/api";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

export function ApplicantDashboardPage() {
  const { data: profile } = useProfile();
  const userProfile = profile?.[0] as UserProfileView;

  const [matches, setMatches] = useState<any[]>([]);

  const loadMatches = async () => {
      if (!userProfile?.business_id) return [];
  
      const { data } = await getBusinessMatches(userProfile.business_id);
  
      if (data) {
        setMatches(data);
        return data;
      }
  
      return [];
    };
  
    useEffect(() => {
      if (userProfile?.business_id) {
        loadMatches();
      }
      console.log(userProfile)

    },[userProfile]);

  return (
    <div>
      <SectionHeader
        title="Applicant Dashboard"
        description="See your profile readiness, latest matches, and next actions in one place."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          label="Profile completeness"
          value={`${userProfile?.profile_completeness ?? 0}%`}
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
          <CardTitle>Recent Matches</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {matches?.slice?.(0, 5)?.map((match) => (
            <Link to={`/app/matches/${match?.program_id}`} key={match?.program_id}>
              <div className="rounded-lg border p-4 mb-2 hover:bg-muted-background transition">
                <div className="mb-2 flex items-center justify-between">
                  <p className="font-semibold">{match?.program_name}</p>
                  <Badge variant={match?.final_score >= 60 ? "success" : "secondary"}>
                    {match?.match_category || "Uncategorized"}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">Match score: {match?.final_score}/100</p>
                <ul className="mt-2 list-disc space-y-1 pl-4 text-sm grid grid-cols-1 md:grid-cols-3 gap-2">
                  {match?.match_reasons?.map((reason: { reason: string }) => (
                    <li key={reason?.reason}>{reason?.reason}</li>
                  ))}
                </ul>
              </div>
            </Link>
          ))}

          {matches?.length === 0 && (
            <p className="text-sm text-muted-foreground">No matches found. Please complete your profile, visit the My Matches page, and check back later.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
