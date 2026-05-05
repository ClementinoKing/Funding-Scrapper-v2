import { useState, useEffect, useRef, useMemo } from "react";
import { SectionHeader } from "@/components/shared/section-header";
import { useProfile } from "@/hooks/use-profile";
import { UserProfileView } from "@/types/api";
import {
  triggerBusinessMatching,
  getBusinessMatches,
} from "@/lib/triggerMatching";
import { supabase } from "@/lib/supabase";
import { Pagination } from "@/components/shared/pagination";
import { ProgramCard } from "@/components/shared/program-card";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";
import { ViewToggle } from "@/components/shared/view-toggle";

export function MatchesPage() {
  const { data: profile } = useProfile();

  const [matches, setMatches] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 12;
  const [viewMode, setViewMode] = useState<"grid" | "list" | "compact">(() => {
    return (
      (localStorage.getItem("viewMode") as "grid" | "list" | "compact") ||
      "grid"
    );
  });

  const hasTriggeredRef = useRef(false); // prevents duplicate triggers
  const pollingRef = useRef<any>(null);

  const userProfile = profile?.[0] as UserProfileView;

  // ---------------- LOAD MATCHES ----------------

  const loadMatches = async () => {
    if (!userProfile?.business_id) return [];

    const { data } = await getBusinessMatches(userProfile.business_id);

    if (data) {
      setMatches(data);
      return data;
    }

    return [];
  };

  // ---------------- TRIGGER MATCHING ----------------

  const triggerMatching = async (useAI = false) => {
    if (!userProfile?.business_id) return;

    setRefreshing(true);

    const res = await triggerBusinessMatching(userProfile.business_id, useAI);

    if (!res.success) {
      console.error("Failed to enqueue matching job");
    }

    setRefreshing(false);
  };

  // ---------------- POLLING ----------------

  const startPolling = () => {
    if (pollingRef.current) return;

    pollingRef.current = setInterval(async () => {
      const data = await loadMatches();

      // stop polling when results appear
      if (data.length > 0) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }, 3000);
  };

  useEffect(() => {
    if (!userProfile?.business_id) return;

    const channel = supabase
      .channel("matches")
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "program_matches",
          filter: `business_id=eq.${userProfile.business_id}`,
        },
        (payload) => {
          // setMatches((prev) => [payload.new, ...prev]);
          console.log(payload.new);
        },
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [userProfile?.business_id]);

  // ---------------- INIT ----------------

  useEffect(() => {
    if (!userProfile?.business_id) return;

    const init = async () => {
      setLoading(true);

      const existingMatches = await loadMatches();

      // If no matches → trigger job ONCE
      if (existingMatches.length === 0 && !hasTriggeredRef.current) {
        hasTriggeredRef.current = true;

        console.log("Enqueuing matching job...");
        triggerMatching(true); // ❗ NOT awaited

        startPolling();
      }

      setLoading(false);
    };

    init();

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [userProfile?.business_id]);

  // ---------------- OTHERS -------------
  const matchStats = {
    total: matches.length,
    excellent: matches.filter((m) => m.match_score >= 80).length,
    good: matches.filter((m) => m.match_score >= 60 && m.match_score < 80)
      .length,
    averageScore:
      matches.length > 0
        ? Math.round(
            matches.reduce((sum, m) => sum + m.match_score, 0) / matches.length,
          )
        : 0,
  };

  // Pagination
  const paginatedPrograms = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return matches.slice(start, start + itemsPerPage);
  }, [matches, currentPage, itemsPerPage]);

  const totalPages = Math.ceil(matches.length / itemsPerPage);

  // Save view mode preference
  useEffect(() => {
    localStorage.setItem("viewMode", viewMode);
  }, [viewMode]);

  // ---------------- UI ----------------

  return (
    <div>
      <SectionHeader
        title="Match Results"
        description="Computed matches from funding programs."
      />

      {/* Controls Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-2 pt-2">
          <Button
            onClick={() => triggerMatching(true)}
            disabled={refreshing}
            className="gap-2"
          >
            <RefreshCw
              className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh Matches (AI)
          </Button>
          <Button
            variant="outline"
            onClick={() => triggerMatching(false)}
            disabled={refreshing}
            className="gap-2"
          >
            <RefreshCw
              className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`}
            />
            Quick Refresh
          </Button>
          <Button variant="ghost" onClick={loadMatches} disabled={loading}>
            Check Matches
          </Button>
        </div>
        <div className="flex gap-2 items-center">
          {/* <SortDropdown
            value={sortBy}
            onValueChange={setSortBy}
            className="w-[180px]"
          /> */}
          <ViewToggle value={viewMode} onValueChange={setViewMode} />
        </div>
      </div>

      {loading && <p>Loading...</p>}
      {refreshing && <p>Starting matching...</p>}

      {!loading && matches.length === 0 && (
        <p>No matches yet. Matching is in progress...</p>
      )}

      <div
        className={
          viewMode === "list"
            ? "space-y-4"
            : viewMode === "grid"
            ? "grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3"
            : "grid gap-2 grid-cols-1 md:grid-cols-2 lg:grid-cols-4"
        }
      >
        {paginatedPrograms.map((match) => (
          <ProgramCard
            key={match.program_id}
            program={match}
            variant={viewMode}
          />
        ))}
      </div>

      {totalPages > 1 && (
        <div className="mt-6">
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={setCurrentPage}
            itemsPerPage={itemsPerPage}
            totalItems={matches.length}
          />
        </div>
      )}
    </div>
  );
}
