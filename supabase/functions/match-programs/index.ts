/**
 * 
 * Test Body:
 * { "business_id": "business-id", "use_ai": false }
 */

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import OpenAI from "https://esm.sh/openai";

// ======================================================
// CONFIG
// ======================================================

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

// ======================================================
// TYPES
// ======================================================

type ScoreReason = {
  score: number;
  reason: string;
};

type ValidationResult = {
  passed: boolean;
  failures: string[];
};

interface MatchResult {
  business_id: string;
  program_id: string;
  match_reasons: ScoreReason[];
  eligibility_gaps: ScoreReason[];
  rule_score: number;
  ai_score: number;
  final_score: number;
  ai_analysis: string;
  ai_confidence: number;
  match_type: string;
  program_title: string;
  matched_at: string;
}

// ======================================================
// LOGGER
// ======================================================

const logger = {
  info: (msg: string, data?: unknown) =>
    console.log("[INFO]", msg, data || ""),

  error: (msg: string, err?: unknown) =>
    console.error("[ERROR]", msg, err || ""),
};

// ======================================================
// HELPERS
// ======================================================

const embeddingCache = new Map<string, number[]>();

const normalizeArray = (val: unknown): string[] => {
  if (!val) return [];

  if (Array.isArray(val)) {
    return val
      .map((v) => String(v).toLowerCase().trim())
      .filter(Boolean);
  }

  return [String(val).toLowerCase().trim()];
};

const overlapScore = (a: string[], b: string[]) => {
  const matches = a.filter((x) =>
    b.some((y) => y.includes(x) || x.includes(y))
  );

  logger.info("Overlap Score: ", matches.length)
  return matches.length;
};

function cosineSimilarity(a: number[], b: number[]) {
  const dot = a.reduce((sum, val, i) => sum + val * b[i], 0);

  const magA = Math.sqrt(a.reduce((sum, val) => sum + val * val, 0));
  const magB = Math.sqrt(b.reduce((sum, val) => sum + val * val, 0));

  logger.info("Cosine Similarity: ", dot / (magA * magB))

  return dot / (magA * magB);
}

// ======================================================
// INDUSTRY GROUPS
// ======================================================

const INDUSTRY_GROUPS: Record<string, string[]> = {

  agriculture_agroprocessing: [
    "agriculture",
    "agro-processing",
    "agroprocessing",
    "farming",
    "agribusiness",
    "crop production",
    "livestock",
    "horticulture",
    "agritech",
    "food production",
    "forestry"
  ],

  manufacturing: [
    "manufacturing",
    "industrial",
    "production",
    "factory",
    "assembly",
    "processing"
  ],

  technology_it: [
    "technology",
    "it",
    "ict",
    "software",
    "information technology",
    "saas",
    "artificial intelligence",
    "machine learning",
    "fintech",
    "cybersecurity",
    "cloud computing",
    "data science",
    "digital services"
  ],

  tourism_hospitality: [
    "tourism",
    "hospitality",
    "hotel",
    "travel",
    "lodging",
    "guest house",
    "resort",
    "ecotourism"
  ],

  mining_quarrying: [
    "mining",
    "quarrying",
    "minerals",
    "extractives",
    "ore extraction"
  ],

  energy_utilities: [
    "energy",
    "utilities",
    "solar",
    "renewable energy",
    "electricity",
    "power generation",
    "water utilities",
    "gas"
  ],

  healthcare_pharmaceuticals: [
    "healthcare",
    "pharmaceuticals",
    "medical",
    "health services",
    "biotech",
    "hospital",
    "clinic",
    "medicine"
  ],

  education_training: [
    "education",
    "training",
    "edtech",
    "skills development",
    "learning",
    "school",
    "university",
    "vocational"
  ],

  retail_wholesale: [
    "retail",
    "wholesale",
    "commerce",
    "trading",
    "shop",
    "ecommerce",
    "distribution"
  ],

  professional_services: [
    "professional services",
    "consulting",
    "legal",
    "accounting",
    "audit",
    "business advisory",
    "marketing agency"
  ],

  construction_real_estate: [
    "construction",
    "real estate",
    "property development",
    "infrastructure",
    "civil engineering",
    "building"
  ],

  transport_logistics: [
    "transport",
    "logistics",
    "freight",
    "delivery",
    "shipping",
    "courier",
    "supply chain"
  ],

  finance_insurance: [
    "finance",
    "insurance",
    "banking",
    "microfinance",
    "investment",
    "financial services"
  ],

  media_communications: [
    "media",
    "communications",
    "broadcasting",
    "advertising",
    "journalism",
    "public relations",
    "telecommunications"
  ],

  food_beverage: [
    "food",
    "beverage",
    "restaurant",
    "catering",
    "food processing",
    "bakery",
    "drinks"
  ],

  textiles_clothing: [
    "textiles",
    "clothing",
    "fashion",
    "garments",
    "apparel",
    "tailoring"
  ],

  other: [
    "other",
    "miscellaneous",
    "general"
  ]
};

// ======================================================
// INDUSTRY NORMALIZATION
// ======================================================

function normalizeIndustryTerm(
  value: string
): string {

  const normalized =
    String(value)
      .toLowerCase()
      .trim();

  for (
    const [group, terms]
    of Object.entries(INDUSTRY_GROUPS)
  ) {

    const matched = terms.some(term =>
      normalized.includes(term) ||
      term.includes(normalized)
    );

    if (matched) {
      return group;
    }
  }

  return normalized;
}

// ======================================================
// EMBEDDINGS
// ======================================================

async function getEmbedding(
  openai: OpenAI,
  text: string
): Promise<number[]> {

  if (embeddingCache.has(text)) {
    return embeddingCache.get(text)!;
  }

  const response =
    await openai.embeddings.create({
      model: "text-embedding-3-small",
      input: text,
    });

  const embedding =
    response.data[0].embedding;

  embeddingCache.set(text, embedding);

  return embedding;
}

// ======================================================
// SEMANTIC INDUSTRY MATCH
// ======================================================

async function semanticIndustryMatch(
  openai: OpenAI | null,
  businessIndustries: string[],
  programIndustries: string[]
): Promise<boolean> {

  // ---------------- EXACT ----------------

  if (
    overlapScore(
      businessIndustries,
      programIndustries
    ) > 0
  ) {
    return true;
  }

  // ---------------- NORMALIZED ----------------

  const normalizedBusiness =
    businessIndustries.map(normalizeIndustryTerm);

  const normalizedPrograms =
    programIndustries.map(normalizeIndustryTerm);

  if (
    overlapScore(
      normalizedBusiness,
      normalizedPrograms
    ) > 0
  ) {
    return true;
  }

  // ---------------- EMBEDDINGS ----------------

  if (!openai) {
    return false;
  }

  try {

    const bizEmbedding =
      await getEmbedding(
        openai,
        normalizedBusiness.join(", ")
      );

    const progEmbedding =
      await getEmbedding(
        openai,
        normalizedPrograms.join(", ")
      );

    const similarity =
      cosineSimilarity(
        bizEmbedding,
        progEmbedding
      );

    logger.info(
      "Industry semantic similarity",
      similarity
    );

    return similarity >= 0.82;

  } catch (err) {

    logger.error(
      "Semantic industry match failed",
      err
    );

    return false;
  }
}

// ======================================================
// STRICT VALIDATION
// ======================================================

async function validateStrictEligibility(
  openai: OpenAI | null,
  profile: any,
  program: any
): Promise<ValidationResult> {

  const failures: string[] = [];

  // ---------------- LOCATION ----------------

  const provinces =
    normalizeArray(program.provinces);

  const userProvince =
    String(profile.province || "")
      .toLowerCase()
      .trim();

  const locationValid =
    program.geography_scope === "National" ||
    provinces.includes(userProvince);

  if (!locationValid) {
    failures.push("LOCATION_RESTRICTION");
  }

  // ---------------- INDUSTRY ----------------

  const bizIndustry =
    normalizeArray(profile.industry);

  const progIndustry =
    normalizeArray(program.industries);

  const industryValid =
    await semanticIndustryMatch(
      openai,
      bizIndustry,
      progIndustry
    );

  if (!industryValid) {
    failures.push("INDUSTRY_NOT_SUPPORTED");
  }

  // ---------------- FUNDING ----------------

  const min =
    Number(profile.funding_amount_min || 0);

  const max =
    Number(profile.funding_amount_max || min);

  const ticketMin =
    Number(program.ticket_min || 0);

  const ticketMax =
    Number(program.ticket_max || 0);

  const fundingValid =
    max >= ticketMin &&
    min <= ticketMax;

  // if (!fundingValid) {
  //   failures.push("FUNDING_OUT_OF_RANGE");
  // }

  return {
    passed: failures.length === 0,
    failures,
  };
}

// ======================================================
// AI MATCH EVALUATION
// ======================================================
async function evaluateMatchWithAI(
  openai: OpenAI,
  profile: any,
  program: any,
  ruleScore: number,
  reasons: ScoreReason[],
  gaps: ScoreReason[]
): Promise<{
  score: number;
  analysis: string;
  confidence: number;
}> {
  const prompt = `
You are an expert funding advisor.

Evaluate how well a BUSINESS matches a FUNDING PROGRAM.

Return STRICT JSON only:
{
  "score": number (0-100),
  "analysis": string,
  "confidence": number (0-1)
}

GUIDELINES:
- Consider BOTH structured rules AND real-world nuance
- Penalize hard eligibility failures (location, funding range, industry)
- Reward strong strategic fit even if minor gaps exist
- Be conservative: avoid over-scoring weak matches

BUSINESS PROFILE:
${JSON.stringify(profile, null, 2)}

PROGRAM:
${JSON.stringify(program, null, 2)}

RULE SCORE: ${ruleScore}

MATCH STRENGTHS:
${JSON.stringify(reasons, null, 2)}

ELIGIBILITY GAPS:
${JSON.stringify(gaps, null, 2)}
`;

  try {
    const response = await openai.responses.create({
      model: "gpt-4.1-mini",
      input: prompt,
      temperature: 0.2, // reduce randomness
    });

    const text = response.output_text?.trim() || "{}";

    logger.info("AI raw response: ", text)

    const parsed = JSON.parse(text);

    return {
      score: Math.max(0, Math.min(100, parsed.score || 0)),
      analysis: parsed.analysis || "",
      confidence: Math.max(0, Math.min(1, parsed.confidence || 0.5)),
    };
  } catch (err) {
    console.error("AI parsing failed:", err);
    return { score: 0, analysis: "", confidence: 0 };
  }
}

// ======================================================
// SAVE MATCH
// ======================================================

async function saveMatchedProgram(match: MatchResult, supabaseClient: any) {
  logger.info("Program Match to save: ", match)
    const { data: existing } = await supabaseClient
        .from('program_matches')
        .select('*')
        .eq('business_id', match.business_id)
        .eq('program_id', match.program_id)
        .single();

    if (existing) {
    const { error: histError } = await supabaseClient
        .from("program_matches")
        .update(
        {
            business_id: match.business_id,
            program_id: match.program_id,
            program_title: match.program_title,
            final_score: match.final_score,
            rule_score: match.rule_score,
            ai_score: match.ai_score,
            match_reasons: match.match_reasons,
            eligibility_gaps: match.eligibility_gaps,
            ai_analysis: match.ai_analysis,
            ai_confidence: match.ai_confidence,
            match_type: match.match_type,
            created_at: match.matched_at
        }
        )
        .eq('business_id', match.business_id)
        .eq('program_id', match.program_id);

        if(histError) {
            logger.error("Error saving matches to history:", histError);
            return;
        }
    } else {
    const { error: histError } = await supabaseClient
        .from("program_matches")
        .insert(
        {
            business_id: match.business_id,
            program_id: match.program_id,
            program_title: match.program_title,
            final_score: match.final_score,
            rule_score: match.rule_score,
            ai_score: match.ai_score,
            match_reasons: match.match_reasons,
            eligibility_gaps: match.eligibility_gaps,
            ai_analysis: match.ai_analysis,
            ai_confidence: match.ai_confidence,
            match_type: match.match_type,
            created_at: match.matched_at
        }
        );

        if(histError) {
            logger.error("Error saving matches to history:", histError);
            return;
        }
    }
}

// ======================================================
// MAIN SERVER
// ======================================================
logger.info('server started');

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { business_id, use_ai = true } = await req.json();
    logger.info("Request body: ", {business_id, use_ai})

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!
    );

    const openai = use_ai && Deno.env.get("OPENAI_API_KEY")
        ? new OpenAI({ apiKey: Deno.env.get("OPENAI_API_KEY") })
        : null;

    // Fetch business profile
    const { data: profile, error: profileError } = await supabase
      .from("v_business_profile")
      .select("*")
      .eq("business_id", business_id)
      .single();

    if (profileError || !profile) throw new Error("Profile not found");

    logger.info("Profile to match", profile)

    // Fetch programs
    const { data: programs, error: programsError } = await supabase
      .from("funding_programmes")
      .select("*");
      
    if (programsError) {
      throw programsError;
    }

    if (!programs || programs.length === 0) {
      return new Response(
        JSON.stringify({
          success: true,
          matches: [],
          message: "No active programs found",
        }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    const results: MatchResult[] = [];

    for(const program of programs) {
      let score = 0;
      const reasons: ScoreReason[] = [];
      const gaps: ScoreReason[] = [];

      // ----------------------------------------------
      // STRICT VALIDATION
      // ----------------------------------------------
      const validation = await validateStrictEligibility(openai, profile, program);

      if (!validation.passed) {
        logger.info(`Program ${program.program_name} rejected`, validation.failures);
        continue;
      }

      // ---------------- INDUSTRY ---------------- (25)
      score += 25;

      reasons.push({
        score: 25,
        reason: "Industry match",
      });

      // ---------------- LOCATION ---------------- (10)
      score += 10;

      reasons.push({
        score: 10,
        reason: "Location eligible",
      });

      // ---------------- FUNDING ---------------- (20)
      const min = profile.funding_amount_min || 0;
      const max = profile.funding_amount_max || min;

      if (
        program.ticket_min &&
        program.ticket_max &&
        max >= program.ticket_min &&
        min <= program.ticket_max
      ) {
        score += 20;
        reasons.push({ score: 20, reason: "Funding range compatible" });
      } else {
        gaps.push({ score: 20, reason: "Funding mismatch" });
      }

      // ---------------- BUSINESS STAGE ---------------- (10)
      const stage = normalizeArray(program.business_stage_eligibility);
      if (stage.includes(String(profile.business_age_band || "").toLowerCase())) {
        score += 10;
        reasons.push({ score: 10, reason: "Business stage fit" });
      } else {
        gaps.push({ score: 10, reason: "Business Stage mismatch" });
      }

      // ---------------- TURNOVER ---------------- (5)
      if (
        (!program.turnover_min ||
          profile.monthly_income_band >= program.turnover_min) &&
        (!program.turnover_max ||
          profile.monthly_income_band <= program.turnover_max)
      ) {
        score += 5;
        reasons.push({ score: 5, reason: "Turnover within range" });
      } else {
        gaps.push({ score: 5, reason: "Turnover not within range" });
      }

      // ---------------- EMPLOYEES ---------------- (5)
      if (
        (!program.employee_min ||
          profile.team_size >= program.employee_min) &&
        (!program.employee_max ||
          profile.team_size <= program.employee_max)
      ) {
        score += 5;
        reasons.push({ score: 5, reason: "Employee size match" });
      } else {
        gaps.push({ score: 5, reason: "Employee size mismatch" });
      }

      // ---------------- YEARS IN BUSINESS ---------------- (5)
      if (
        (!program.years_in_business_min ||
          profile.years_in_business >= program.years_in_business_min) &&
        (!program.years_in_business_max ||
          profile.years_in_business <= program.years_in_business_max)
      ) {
        score += 5;
        reasons.push({ score: 5, reason: "Experience matches" });
      } else {
        gaps.push({ score: 5, reason: "Experience mismatch" });
      }

      // ---------------- USE OF FUNDS ---------------- (10)
      const needs = normalizeArray(profile.funding_needs);
      const uses = normalizeArray(program.use_of_funds);

      if (overlapScore(needs, uses) > 0) {
        score += 10;
        reasons.push({ score: 10, reason: "Funding purpose aligned" });
      } else {
        gaps.push({ score: 10, reason: "Funding purpose mismatch" });
      }

      // ---------------- CERTIFICATIONS ---------------- (5)
      const certs = normalizeArray(program.certifications_required);
      if (certs.length === 0 || certs.includes(profile.bbee_certification?.toLowerCase())) {
        score += 5;
        reasons.push({ score: 5, reason: "Certification acceptable" });
      } else {
        gaps.push({ score: 5, reason: "Certification missing" });
      }

      // ---------------- OWNERSHIP TARGET ---------------- (5)
      const ownership = normalizeArray(program.ownership_targets);
      if (ownership.length === 0) {
        score += 5;
        reasons.push({ score: 5, reason: "Ownership target acceptable" });
      } else {
        gaps.push({ score: 5, reason: "Ownership target not supported" });
      }

      logger.info("Match Score: ", score)

      // ---------------- AI ----------------
      let aiScore = 0;
      let aiAnalysis = "";
      let aiConfidence = 0;

      if (openai && score >= 40) {
        try {
          const aiResult = await evaluateMatchWithAI(
            openai,
            profile,
            program,
            score,
            reasons,
            gaps
          );

          aiScore = aiResult.score;
          aiAnalysis = aiResult.analysis;
          aiConfidence = aiResult.confidence;

          logger.info("AI Score:", aiScore);
        } catch (e) {
          logger.error("AI failed", e);
        }
      }

      let finalScore = score;

      if (use_ai && aiConfidence > 0.6) {
        const weight = 0.5 + (aiConfidence * 0.3); 
        finalScore = Math.round(
          (score * (1 - weight)) + 
          (aiScore * weight)
        );
      } else {
        finalScore = score;
      }

      logger.info("Match Reasons for " + business_id, reasons)
      logger.info("Gaps for " + business_id, gaps)
      logger.info("Final Score: ", finalScore)

      const result = {
        business_id,
        program_id: program.program_id,
        program_title: program.program_name,
        rule_score: score,
        ai_score: aiScore,
        final_score: finalScore,
        match_reasons: reasons,
        eligibility_gaps: gaps,
        ai_analysis: aiAnalysis,
        ai_confidence: aiConfidence,
        match_type: aiScore ? "hybrid" : "rule",
        matched_at: new Date().toISOString(),
      };
      results.push(result);

      await saveMatchedProgram(result, supabase);

    }

    results.sort((a, b) => b.final_score - a.final_score);

    return new Response(JSON.stringify({ matches: results }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
    
  } catch (error: any) {
    logger.error(
      "Processing error",
      error
    );

    return new Response(
      JSON.stringify({
        success: false,
        error:
          error?.message ||
          "Unknown error",
      }),
      {
        status: 500,
        headers: {
          ...corsHeaders,
          "Content-Type":
            "application/json",
        },
      }
    );
  }
});