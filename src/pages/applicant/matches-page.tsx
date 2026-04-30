import {useState, useEffect} from "react";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useProfile } from "@/hooks/use-profile";
import { UserProfileView } from "@/types/api";
import {
  triggerBusinessMatching,
  checkPendingMatches,
  getBusinessMatches,
} from "@/lib/triggerMatching";

export function MatchesPage() {
  const { data: profile } = useProfile();
  const [matches, setMatches] = useState<unknown[]>([]);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [polling, setPolling] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  const userProfile = profile?.[0] as UserProfileView;
  console.log(userProfile)

  const loadMatchStatus = async () => {
  if (!userProfile?.business_id) return false;

  setLoading(true);

  const { hasPending } = await checkPendingMatches(
    userProfile.business_id
  );

  setPending(hasPending);

  const { data: matchesData } = await getBusinessMatches(
    userProfile.business_id
  );

  if (matchesData) {
    setMatches(matchesData);
    if (matchesData.length > 0) {
      setLastUpdated(matchesData[0].created_at);
    }
  }

  if (
    !pending &&
    !refreshing &&
    (!matches || matches.length === 0)
  ) {
    console.log("Triggering matching...");
    await triggerMatching();
    return true;
  }

  setLoading(false);

  return hasPending;
};

  const triggerMatching = async (useAI = true) => {
    if(!userProfile?.business_id) return;
    
    setRefreshing(true);

    const result = await triggerBusinessMatching(
      userProfile?.business_id,
      useAI,
    );

    if (result.success) {
      await loadMatchStatus();
    }

    setRefreshing(false);
  };

  useEffect(() => {
  if (!userProfile?.business_id) return;

  let interval: any;

  const init = async () => {
    const isPending = await loadMatchStatus();

    // Trigger if nothing exists
    if (!isPending && matches.length === 0) {
      await triggerMatching();
    }

    interval = setInterval(async () => {
      const stillPending = await loadMatchStatus();

      if (!stillPending) {
        clearInterval(interval);
      }
    }, 3000);
  };

  init();

  return () => {
    if (interval) clearInterval(interval);
  };
}, [userProfile?.business_id]);

  return (
    <div>
      <SectionHeader
        title="Match Results"
        description="Instantly computed matches from normalized funding records in the central database."
      />
      <div className="space-y-4">
        {/* {matches.map((match) => (
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
        ))} */}
      </div>
    </div>
  );
}
