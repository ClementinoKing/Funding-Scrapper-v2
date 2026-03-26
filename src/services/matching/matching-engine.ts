import type { ApplicantProfile, FundingProgram, MatchResult } from "@/types/domain";

export function computeMatchPreview(
  profile: ApplicantProfile,
  programs: FundingProgram[]
): MatchResult[] {
  return programs.map((program) => {
    const reasons: string[] = [];
    const blockers: string[] = [];
    let score = 0;

    const sectorOverlap = profile.sectors.filter((sector) =>
      program.sectors.some((programSector) =>
        programSector.toLowerCase().includes(sector.toLowerCase())
      )
    );

    if (sectorOverlap.length > 0) {
      score += 35;
      reasons.push(`Sector overlap: ${sectorOverlap.join(", ")}`);
    }

    const geographyEligible = program.geography.some((region) =>
      [region.toLowerCase(), profile.country.toLowerCase()].some((value) =>
        value.includes("africa") || value.includes("malawi")
      )
    );

    if (geographyEligible) {
      score += 30;
      reasons.push("Geography appears eligible");
    } else {
      blockers.push("Geography may be out of scope");
    }

    if (profile.preferredFundingTypes.includes(program.fundingType)) {
      score += 20;
      reasons.push("Funding type aligned to profile preference");
    }

    if (
      profile.targetAmountMin !== undefined &&
      profile.targetAmountMax !== undefined &&
      program.amountMin !== undefined &&
      program.amountMax !== undefined &&
      program.amountMax >= profile.targetAmountMin &&
      program.amountMin <= profile.targetAmountMax
    ) {
      score += 15;
      reasons.push("Funding amount range overlaps");
    }

    const status: MatchResult["status"] =
      score >= 80
        ? "high_fit"
        : score >= 60
          ? "medium_fit"
          : blockers.length > 0
            ? "manual_review"
            : "low_fit";

    return {
      id: `preview_${program.id}`,
      userId: profile.userId,
      programId: program.id,
      score,
      reasons,
      blockers,
      status,
      updatedAt: new Date().toISOString()
    };
  });
}
