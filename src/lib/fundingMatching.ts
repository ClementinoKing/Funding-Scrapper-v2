import type { ApplicantProfile } from "@/types/domain";
import type { BusinessProfile, ScrapedFundingProgramme } from "@/types/funding";

const normalizeText = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const unique = (values: string[]): string[] => {
  const seen = new Set<string>();
  return values.filter((value) => {
    const key = normalizeText(value);
    if (!key || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
};

const hasAnyMatch = (haystack: string, needles: string[]): boolean => {
  const normalizedHaystack = normalizeText(haystack);
  return needles.some((needle) => {
    const normalizedNeedle = normalizeText(needle);
    return normalizedNeedle ? normalizedHaystack.includes(normalizedNeedle) : false;
  });
};

const listHasAnyMatch = (haystack: string[], needles: string[]): boolean =>
  haystack.some((value) => hasAnyMatch(value, needles));

const extractNumber = (value?: number | string | null): number | undefined => {
  if (value === null || value === undefined || value === "") {
    return undefined;
  }
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : undefined;
};

const rangesOverlap = (
  leftMin?: number | null,
  leftMax?: number | null,
  rightMin?: number | null,
  rightMax?: number | null
): boolean => {
  const leftLower = extractNumber(leftMin);
  const leftUpper = extractNumber(leftMax);
  const rightLower = extractNumber(rightMin);
  const rightUpper = extractNumber(rightMax);

  if (leftLower === undefined && leftUpper === undefined) {
    return false;
  }
  if (rightLower === undefined && rightUpper === undefined) {
    return false;
  }

  const normalizedLeftLower = leftLower ?? leftUpper ?? 0;
  const normalizedLeftUpper = leftUpper ?? leftLower ?? normalizedLeftLower;
  const normalizedRightLower = rightLower ?? rightUpper ?? 0;
  const normalizedRightUpper = rightUpper ?? rightLower ?? normalizedRightLower;

  return normalizedLeftLower <= normalizedRightUpper && normalizedRightLower <= normalizedLeftUpper;
};

const stageKeywords: Record<string, string[]> = {
  idea: ["idea", "concept", "startup", "seed", "early stage", "pre-seed"],
  early: ["early stage", "startup", "seed", "pilot", "trading less than"],
  growth: ["growth", "scale", "expansion", "established", "series a"],
  established: ["established", "mature", "scale", "expansion"]
};

export const mapApplicantProfileToBusinessProfile = (
  profile: ApplicantProfile
): BusinessProfile => ({
  userId: profile.userId,
  country: profile.country,
  province: profile.region,
  municipality: profile.region,
  sectors: profile.sectors,
  stage: profile.stage,
  ownershipTargets: [],
  useOfFunds: profile.fundingNeeds,
  yearsOperating: profile.yearsOperating,
  requestedFundingMin: profile.targetAmountMin,
  requestedFundingMax: profile.targetAmountMax,
  preferredFundingTypes: profile.preferredFundingTypes,
  organizationType: profile.organizationType
});

export const normalizeBusinessProfile = (profile?: BusinessProfile | ApplicantProfile | null): BusinessProfile | undefined => {
  if (!profile) {
    return undefined;
  }
  if ("fullName" in profile) {
    return mapApplicantProfileToBusinessProfile(profile as ApplicantProfile);
  }
  return {
    ...profile,
    sectors: unique(profile.sectors ?? []),
    ownershipTargets: unique(profile.ownershipTargets ?? []),
    useOfFunds: unique(profile.useOfFunds ?? []),
    preferredFundingTypes: unique((profile.preferredFundingTypes ?? []) as string[]) as BusinessProfile["preferredFundingTypes"]
  };
};

export const programmeHasGeographyMatch = (
  programme: ScrapedFundingProgramme,
  profile?: BusinessProfile
): boolean => {
  if (!profile) {
    return false;
  }

  const programmeGeography = unique([
    ...(programme.provinces ?? []),
    ...(programme.municipalities ?? []),
    programme.geographyScope ?? ""
  ]);

  if (!programmeGeography.length) {
    return false;
  }

  const profileCandidates = unique(
    [profile.country, profile.province, profile.municipality].filter(Boolean) as string[]
  );

  if (programmeGeography.some((value) => normalizeText(value) === "national")) {
    return true;
  }

  return profileCandidates.some((candidate) =>
    programmeGeography.some((value) => normalizeText(value).includes(normalizeText(candidate)))
  );
};

export const programmeMatchesIndustry = (
  programme: ScrapedFundingProgramme,
  profile?: BusinessProfile
): boolean => {
  if (!profile?.sectors?.length) {
    return false;
  }

  const programmeIndustries = unique([
    ...(programme.industries ?? []),
    ...(programme.useOfFunds ?? []),
    ...(programme.businessStageEligibility ?? []),
    ...(programme.rawEligibilityData ? [Array.isArray(programme.rawEligibilityData) ? programme.rawEligibilityData.join(" ") : programme.rawEligibilityData] : [])
  ].filter(Boolean) as string[]);

  return profile.sectors.some((sector) => programmeIndustries.some((industry) => hasAnyMatch(industry, [sector])));
};

export const programmeMatchesAmount = (
  programme: ScrapedFundingProgramme,
  profile?: BusinessProfile
): boolean => {
  if (!profile?.requestedFundingMin && !profile?.requestedFundingMax) {
    return false;
  }
  return rangesOverlap(
    programme.amountMin,
    programme.amountMax,
    profile.requestedFundingMin,
    profile.requestedFundingMax
  );
};

export const programmeMatchesStage = (
  programme: ScrapedFundingProgramme,
  profile?: BusinessProfile
): boolean => {
  if (!profile?.stage) {
    return false;
  }
  const keywords = stageKeywords[String(profile.stage)] ?? stageKeywords.early;
  return listHasAnyMatch(programme.businessStageEligibility ?? [], keywords);
};

export const programmeMatchesOwnership = (
  programme: ScrapedFundingProgramme,
  profile?: BusinessProfile
): boolean => {
  const profileTargets = unique(profile?.ownershipTargets ?? []);
  if (!profileTargets.length) {
    return false;
  }
  return listHasAnyMatch(programme.ownershipTargets ?? [], profileTargets);
};

export const programmeMatchesUseOfFunds = (
  programme: ScrapedFundingProgramme,
  profile?: BusinessProfile
): boolean => {
  const requestedUses = unique(profile?.useOfFunds ?? []);
  if (!requestedUses.length) {
    return false;
  }

  const programmeUses = unique([...(programme.useOfFunds ?? []), ...(programme.fundingLines ?? [])]);
  return requestedUses.some((use) => programmeUses.some((candidate) => hasAnyMatch(candidate, [use])));
};

export const programmeMatchesBusinessRules = (
  programme: ScrapedFundingProgramme,
  profile?: BusinessProfile
): boolean => {
  if (!profile) {
    return false;
  }

  return (
    programmeMatchesIndustry(programme, profile) ||
    programmeMatchesAmount(programme, profile) ||
    programmeMatchesStage(programme, profile) ||
    programmeMatchesOwnership(programme, profile) ||
    programmeMatchesUseOfFunds(programme, profile) ||
    programmeHasGeographyMatch(programme, profile)
  );
};

export const ownershipTargetBadges = (programme: ScrapedFundingProgramme): string[] => {
  const tags = unique(programme.ownershipTargets ?? []);
  return tags.flatMap((tag) => {
    const normalized = normalizeText(tag);
    if (normalized.includes("youth")) return ["Youth-owned eligible"];
    if (normalized.includes("women")) return ["Women-owned eligible"];
    if (normalized.includes("black")) return ["Black-owned eligible"];
    if (normalized.includes("disabled")) return ["Disabled-owned eligible"];
    if (normalized.includes("township")) return ["Township businesses"];
    if (normalized.includes("rural")) return ["Rural enterprises"];
    return [tag];
  });
};

export { extractNumber, hasAnyMatch, listHasAnyMatch, normalizeText, rangesOverlap, unique };
