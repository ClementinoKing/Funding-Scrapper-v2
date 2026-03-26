import type { BusinessProfile, ProgrammeScoreBreakdown, ScoredProgramme, ScrapedFundingProgramme } from "@/types/funding";
import {
  normalizeText,
  normalizeBusinessProfile,
  programmeHasGeographyMatch,
  programmeMatchesAmount,
  programmeMatchesIndustry,
  programmeMatchesOwnership,
  programmeMatchesStage,
  programmeMatchesUseOfFunds,
  unique
} from "@/lib/fundingMatching";

const clamp = (value: number, min: number, max: number): number => Math.min(max, Math.max(min, value));

const toNumber = (value?: number | string | null): number | undefined => {
  if (value === null || value === undefined || value === "") {
    return undefined;
  }
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : undefined;
};

const isKnownFundingType = (value?: string | null): boolean => {
  if (!value) {
    return false;
  }
  return !["unknown", "other"].includes(normalizeText(value)) || normalizeText(value) === "other";
};

const isOpenDeadline = (programme: ScrapedFundingProgramme): boolean => {
  const deadlineType = normalizeText(programme.deadlineType ?? "");
  if (["open", "rolling"].includes(deadlineType)) {
    return true;
  }

  if (!programme.deadlineDate) {
    return false;
  }

  const deadline = new Date(programme.deadlineDate);
  return !Number.isNaN(deadline.getTime()) && deadline.getTime() >= Date.now();
};

const hasApplicationRoute = (programme: ScrapedFundingProgramme): boolean =>
  Boolean(
    programme.applicationChannel ||
      programme.applicationUrl ||
      programme.contactEmail ||
      programme.contactPhone
  );

const hasEligibilityDetails = (programme: ScrapedFundingProgramme): boolean =>
  Boolean(
    (programme.rawEligibilityData && (Array.isArray(programme.rawEligibilityData)
      ? programme.rawEligibilityData.length
      : String(programme.rawEligibilityData).trim())) ||
      (programme.businessStageEligibility?.length ?? 0) > 0 ||
      (programme.entityTypesAllowed?.length ?? 0) > 0 ||
      (programme.certificationsRequired?.length ?? 0) > 0
  );

interface ScoreSignal {
  score: number;
  reasons: string[];
  blockers: string[];
}

const analyseQuality = (programme: ScrapedFundingProgramme): ScoreSignal => {
  let score = 0;
  const reasons: string[] = [];
  const blockers: string[] = [];

  if (programme.title?.trim() || programme.program_name?.trim()) {
    score += 12;
    reasons.push("Has programme name");
  } else {
    score -= 15;
    blockers.push("Missing programme name");
  }

  if (programme.providerName?.trim() || programme.funder_name?.trim()) {
    score += 10;
    reasons.push("Has funder name");
  } else {
    score -= 10;
    blockers.push("Missing funder name");
  }

  if (isKnownFundingType(programme.fundingType || programme.funding_type)) {
    score += 8;
    reasons.push("Known funding type");
  } else {
    score -= 8;
    blockers.push("Unknown funding type");
  }

  if (toNumber(programme.amountMin) !== undefined || toNumber(programme.amountMax) !== undefined) {
    score += 8;
    reasons.push("Funding range available");
  } else {
    score -= 4;
  }

  if ((programme.industries?.length ?? 0) > 0) {
    score += 8;
    reasons.push("Industry information captured");
  }

  if ((programme.useOfFunds?.length ?? 0) > 0 || (programme.fundingLines?.length ?? 0) > 0) {
    score += 6;
    reasons.push("Use of funds captured");
  }

  if ((programme.ownershipTargets?.length ?? 0) > 0) {
    score += 5;
    reasons.push("Ownership targets captured");
  }

  if (hasEligibilityDetails(programme)) {
    score += 8;
    reasons.push("Eligibility details captured");
  }

  if (programme.applicationChannel && normalizeText(programme.applicationChannel) !== "unknown") {
    score += 8;
    reasons.push("Application route available");
  } else {
    score -= 10;
    blockers.push("Missing application route");
  }

  if (hasApplicationRoute(programme)) {
    score += 8;
    reasons.push("Contact or apply link available");
  } else {
    score -= 8;
    blockers.push("Missing application contact");
  }

  if (isOpenDeadline(programme)) {
    score += 10;
    reasons.push("Open or active deadline");
  } else if (programme.deadlineDate) {
    const deadline = new Date(programme.deadlineDate);
    if (!Number.isNaN(deadline.getTime()) && deadline.getTime() < Date.now()) {
      score -= 15;
      blockers.push("Expired deadline");
    }
  }

  if ((programme.geography ?? []).length > 0 || (programme.provinces ?? []).length > 0 || (programme.municipalities ?? []).length > 0) {
    score += 5;
    reasons.push("Geography captured");
  }

  if ((programme.relatedDocuments?.length ?? 0) > 0) {
    score += 4;
    reasons.push("Supporting documents linked");
  }

  const completenessSignals = [
    programme.title?.trim(),
    programme.providerName?.trim(),
    programme.fundingType,
    programme.amountMin !== undefined || programme.amountMax !== undefined,
    programme.industries?.length,
    programme.useOfFunds?.length,
    programme.applicationChannel,
    hasApplicationRoute(programme)
  ].filter(Boolean).length;

  if (completenessSignals <= 3) {
    score -= 12;
    blockers.push("Mostly incomplete record");
  }

  return {
    score: clamp(score, 0, 100),
    reasons: unique(reasons),
    blockers: unique(blockers)
  };
};

const analyseMatch = (
  programme: ScrapedFundingProgramme,
  profile?: BusinessProfile
): ScoreSignal => {
  if (!profile) {
    return { score: 0, reasons: [], blockers: [] };
  }

  let score = 0;
  const reasons: string[] = [];
  const blockers: string[] = [];

  if (programmeMatchesIndustry(programme, profile)) {
    score += 28;
    reasons.push("Strong industry match");
  } else if (profile.sectors.length > 0) {
    score -= 10;
    blockers.push("No clear industry match");
  }

  if (programmeHasGeographyMatch(programme, profile)) {
    score += 20;
    if (profile.province || profile.municipality || profile.country) {
      reasons.push("Geography match");
    }
  } else if (profile.province || profile.municipality || profile.country) {
    score -= 18;
    blockers.push("Geography may be out of scope");
  }

  if (programmeMatchesAmount(programme, profile)) {
    score += 18;
    reasons.push("Within funding range");
  } else if (profile.requestedFundingMin !== undefined || profile.requestedFundingMax !== undefined) {
    score -= 20;
    blockers.push("Requested amount may not fit this programme");
  }

  if (programmeMatchesStage(programme, profile)) {
    score += 10;
    reasons.push("Business stage match");
  }

  if (programmeMatchesOwnership(programme, profile)) {
    score += 10;
    reasons.push("Ownership target match");
  }

  if (programmeMatchesUseOfFunds(programme, profile)) {
    score += 10;
    reasons.push("Use-of-funds match");
  }

  const yearsInBusiness = profile.yearsOperating;
  const programmeYearsMin = toNumber(programme.yearsInBusinessMin);
  const programmeYearsMax = toNumber(programme.yearsInBusinessMax);
  if (
    yearsInBusiness !== undefined &&
    programmeYearsMin !== undefined &&
    programmeYearsMax !== undefined &&
    yearsInBusiness >= programmeYearsMin &&
    yearsInBusiness <= programmeYearsMax
  ) {
    score += 6;
    reasons.push("Years-in-business match");
  }

  const programmeTurnoverMin = toNumber(programme.turnoverMin);
  const programmeTurnoverMax = toNumber(programme.turnoverMax);
  if (
    profile.turnoverMin !== undefined &&
    profile.turnoverMax !== undefined &&
    programmeTurnoverMin !== undefined &&
    programmeTurnoverMax !== undefined &&
    profile.turnoverMin <= programmeTurnoverMax &&
    profile.turnoverMax >= programmeTurnoverMin
  ) {
    score += 6;
    reasons.push("Turnover range overlaps");
  }

  const programmeEmployeeMin = toNumber(programme.employeeMin);
  const programmeEmployeeMax = toNumber(programme.employeeMax);
  if (
    profile.employeeCount !== undefined &&
    programmeEmployeeMin !== undefined &&
    programmeEmployeeMax !== undefined &&
    profile.employeeCount >= programmeEmployeeMin &&
    profile.employeeCount <= programmeEmployeeMax
  ) {
    score += 6;
    reasons.push("Employee count match");
  }

  const preferredFundingTypes = profile.preferredFundingTypes?.map((type) => normalizeText(type)) ?? [];
  const programmeFundingType = normalizeText(programme.fundingType || "");
  if (preferredFundingTypes.length && preferredFundingTypes.includes(programmeFundingType)) {
    score += 8;
    reasons.push("Preferred funding type");
  }

  return {
    score: clamp(score, 0, 100),
    reasons: unique(reasons),
    blockers: unique(blockers)
  };
};

export function scoreProgrammeQuality(programme: ScrapedFundingProgramme): number {
  return analyseQuality(programme).score;
}

export function scoreProgrammeMatch(programme: ScrapedFundingProgramme, businessProfile?: BusinessProfile): number {
  return analyseMatch(programme, normalizeBusinessProfile(businessProfile)).score;
}

export function getProgrammeReasonTags(
  programme: ScrapedFundingProgramme,
  businessProfile?: BusinessProfile
): string[] {
  const quality = analyseQuality(programme);
  const match = analyseMatch(programme, normalizeBusinessProfile(businessProfile));
  const combined = [
    ...match.reasons,
    ...quality.reasons,
    ...(match.score < 50 ? match.blockers : []),
    ...(quality.score < 50 ? quality.blockers : [])
  ];
  return unique(combined).slice(0, 6);
}

export function scoreProgramme(
  programme: ScrapedFundingProgramme,
  businessProfile?: BusinessProfile
): ScoredProgramme {
  const normalizedProfile = normalizeBusinessProfile(businessProfile);
  const quality = analyseQuality(programme);
  const match = analyseMatch(programme, normalizedProfile);
  const importanceScore = normalizedProfile ? Math.round(quality.score * 0.4 + match.score * 0.6) : quality.score;
  const reasonTags = getProgrammeReasonTags(programme, normalizedProfile);
  const scoreBand: ProgrammeScoreBreakdown["scoreBand"] =
    importanceScore >= 75 ? "high" : importanceScore >= 45 ? "medium" : "low";

  return {
    ...programme,
    qualityScore: quality.score,
    matchScore: match.score,
    importanceScore,
    qualityReasons: quality.reasons,
    matchReasons: match.reasons,
    blockers: unique([...quality.blockers, ...match.blockers]),
    reasonTags,
    scoreBand
  };
}

export function rankProgrammes(
  programmes: ScrapedFundingProgramme[],
  businessProfile?: BusinessProfile
): ScoredProgramme[] {
  return programmes
    .map((programme) => scoreProgramme(programme, businessProfile))
    .sort((left, right) => {
      if (right.importanceScore !== left.importanceScore) {
        return right.importanceScore - left.importanceScore;
      }
      if (right.qualityScore !== left.qualityScore) {
        return right.qualityScore - left.qualityScore;
      }
      if (right.matchScore !== left.matchScore) {
        return right.matchScore - left.matchScore;
      }
      return (left.title || left.program_name || "").localeCompare(right.title || right.program_name || "");
    });
}

export const getScoreTone = (score: number): "high" | "medium" | "low" =>
  score >= 75 ? "high" : score >= 45 ? "medium" : "low";
