import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { format } from "date-fns";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/services/api/client";
import type { FundingProgram } from "@/types/domain";
import type { ScrapedFundingProgramme } from "@/types/funding";

const formatDeadline = (program: FundingProgram): string => {
  if (program.deadlineAt) {
    const date = new Date(program.deadlineAt);
    return Number.isNaN(date.getTime()) ? "Deadline not specified" : `Deadline ${format(date, "PPP")}`;
  }
  if (program.status === "closed") {
    return "Closed";
  }
  return "Rolling / open";
};

const formatMoney = (value?: number): string => {
  if (value === undefined || Number.isNaN(value)) {
    return "Not specified";
  }
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
    maximumFractionDigits: 0
  }).format(value);
};

function ProgrammeCard({ program }: { program: ScrapedFundingProgramme }) {
  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="text-base">{program.title}</CardTitle>
            <p className="text-sm text-muted-foreground">{program.providerName}</p>
          </div>
          <Badge variant={program.status === "active" ? "success" : program.status === "closing_soon" ? "warning" : "secondary"}>
            {program.status}
          </Badge>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{program.fundingType}</Badge>
          <Badge variant="outline">{formatDeadline(program)}</Badge>
          <Badge variant="outline">
            {formatMoney(program.amountMin)}
            {program.amountMax ? ` - ${formatMoney(program.amountMax)}` : ""}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">{program.eligibilitySummary}</p>
        <div className="flex flex-wrap gap-2">
          {program.geography.slice(0, 3).map((item) => (
            <Badge key={item} variant="outline">
              {item}
            </Badge>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 pt-2">
          <Button asChild variant="outline" size="sm">
            <Link to={`/app/programs/${program.id}`}>Open full page</Link>
          </Button>
          <Button asChild size="sm">
            <a href={program.sourceUrl} target="_blank" rel="noreferrer">
              Open source
            </a>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function ProgramsPage() {
  const [query, setQuery] = useState("");
  const { data: programs = [] } = useQuery({
    queryKey: ["programs"],
    queryFn: apiClient.getPrograms
  });

  const filteredPrograms = useMemo(() => {
    const terms = query.toLowerCase().trim();
    return programs
      .filter((program) => {
        if (!terms) return true;
        return [program.title, program.providerName, program.eligibilitySummary, ...program.geography].join(" ")
          .toLowerCase()
          .includes(terms);
      })
      .sort((left, right) => left.title.localeCompare(right.title));
  }, [programs, query]);

  return (
    <div className="space-y-8">
      <SectionHeader
        title="Funding Programs"
        description="Browse the current funding programme catalogue."
      />
      <div className="mb-4 max-w-md">
        <Input placeholder="Filter by title, provider, or sector..." value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {filteredPrograms.map((program) => (
          <ProgrammeCard key={program.id} program={program} />
        ))}
      </div>
    </div>
  );
}
