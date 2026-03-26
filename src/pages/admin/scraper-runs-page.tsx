import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { apiClient } from "@/services/api/client";

export function ScraperRunsPage() {
  const { data: runs = [] } = useQuery({
    queryKey: ["scrape-runs"],
    queryFn: apiClient.getScrapeRuns
  });

  return (
    <div>
      <SectionHeader
        title="Scraper Health and Runs"
        description="Track cron-driven scraping pipelines, source reliability, and records flagged for human intervention."
      />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Run ID</TableHead>
            <TableHead>Source</TableHead>
            <TableHead>Started</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Found/Stored/Flagged</TableHead>
            <TableHead>Error</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run) => (
            <TableRow key={run.id}>
              <TableCell className="font-medium">{run.id}</TableCell>
              <TableCell>{run.sourceName}</TableCell>
              <TableCell>{format(new Date(run.startedAt), "PPP p")}</TableCell>
              <TableCell>
                <Badge variant={run.status === "success" ? "success" : "warning"}>{run.status}</Badge>
              </TableCell>
              <TableCell>{run.recordsFound}/{run.recordsStored}/{run.recordsFlagged}</TableCell>
              <TableCell className="text-muted-foreground">{run.errorSummary ?? "-"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
