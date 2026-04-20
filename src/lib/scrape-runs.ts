import type { ScrapeRun } from "@/types/domain";

export const getScrapeRunStatusVariant = (
  status: ScrapeRun["status"]
): "success" | "warning" | "secondary" => {
  if (status === "success") {
    return "success";
  }

  if (status === "failed" || status === "partial") {
    return "warning";
  }

  return "secondary";
};

export const getScrapeRunStatusTone = (status: ScrapeRun["status"]): string => {
  if (status === "success") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }

  if (status === "failed") {
    return "border-rose-200 bg-rose-50 text-rose-700";
  }

  if (status === "partial") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }

  return "border-slate-200 bg-slate-50 text-slate-700";
};

export const formatScrapeRunStatus = (status: ScrapeRun["status"]): string =>
  status.charAt(0).toUpperCase() + status.slice(1);

export const getScrapeRunDurationMs = (run: Pick<ScrapeRun, "startedAt" | "completedAt">): number | undefined => {
  if (!run.completedAt) {
    return undefined;
  }

  const started = new Date(run.startedAt).getTime();
  const completed = new Date(run.completedAt).getTime();

  if (Number.isNaN(started) || Number.isNaN(completed) || completed < started) {
    return undefined;
  }

  return completed - started;
};

export const formatScrapeRunDuration = (
  run: Pick<ScrapeRun, "startedAt" | "completedAt">
): string => {
  const durationMs = getScrapeRunDurationMs(run);

  if (durationMs === undefined) {
    return "Still running";
  }

  const totalSeconds = Math.round(durationMs / 1000);

  if (totalSeconds < 60) {
    return `${totalSeconds}s`;
  }

  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }

  if (minutes > 0 && seconds === 0) {
    return `${minutes}m`;
  }

  return `${minutes}m ${seconds}s`;
};

export const getScrapeRunIssueCount = (run: Pick<ScrapeRun, "warnings" | "errors">): number =>
  run.warnings.length + run.errors.length;

export const getScrapeRunFetchRate = (
  run: Pick<ScrapeRun, "urlsCrawled" | "pagesFetchedSuccessfully">
): number => {
  if (run.urlsCrawled <= 0) {
    return 0;
  }

  return Math.round((run.pagesFetchedSuccessfully / run.urlsCrawled) * 100);
};
