import { useQuery } from "@tanstack/react-query";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/services/api/client";

export function MatchesPage() {
  const { data: matches = [] } = useQuery({
    queryKey: ["matches"],
    queryFn: () => apiClient.getMatchesByUser("user_001")
  });

  return (
    <div>
      <SectionHeader
        title="Match Results"
        description="Instantly computed matches from normalized funding records in the central database."
      />
      <div className="space-y-4">
        {matches.map((match) => (
          <Card key={match.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Program {match.programId}</CardTitle>
                <Badge variant={match.status === "high_fit" ? "success" : "secondary"}>{match.status}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm font-semibold">Score: {match.score}/100</p>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold uppercase text-muted-foreground">Why this matches</p>
                  <ul className="mt-1 list-disc pl-5 text-sm">
                    {match.reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase text-muted-foreground">Blockers</p>
                  <ul className="mt-1 list-disc pl-5 text-sm">
                    {match.blockers.length === 0 ? <li>No blockers detected.</li> : match.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
