/**
 * 
 * Test Body:
 * { "business_id": "business-id", "use_ai": false }
 */

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import OpenAI from "https://esm.sh/openai";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

// TYPES
type ScoreReason = {
  score: number;
  reason: string;
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

// HELPERS

const logger = {
  info: (msg: string, data?: unknown) => console.log("[INFO]", msg, data || ""),
  error: (msg: string, err?: unknown) => console.error("[ERROR]", msg, err || ""),
};

const normalizeArray = (val: unknown): string[] => {
  if (!val) return [];
  if (Array.isArray(val)) return val.map((v) => String(v).toLowerCase());
  return [String(val).toLowerCase()];
};

const overlapScore = (a: string[], b: string[]) => {
  const matches = a.filter((x) =>
    b.some((y) => y.includes(x) || x.includes(y))
  );
  return matches.length;
};

logger.info('server started');

// MAIN MATCHING FUNCTION
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

    // Fetch business profile
    const { data: profile } = await supabase
      .from("v_business_profile")
      .select("*")
      .eq("business_id", business_id)
      .single();

    if (!profile) throw new Error("Profile not found");

    logger.info("Profile to match", profile)

    // Fetch programs
    const { data: programs } = await supabase
      .from("funding_programmes")
      .select("*");

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

      // ---------------- INDUSTRY ---------------- (25)
      const bizIndustry = normalizeArray(profile.industry);
      const progIndustry = normalizeArray(program.industries);

      const indScore = overlapScore(bizIndustry, progIndustry);

      if (indScore > 0) {
        score += 25;
        reasons.push({ score: 25, reason: "Industry match" });
      } else {
        gaps.push({ score: 25, reason: "Industry not supported" });
      }

      // ---------------- LOCATION ---------------- (10)
      const provinces = normalizeArray(program.provinces);
      const userProvince = (profile.province || "").toLowerCase();

      if (
        program.geography_scope === "National" ||
        provinces.includes(userProvince)
      ) {
        score += 10;
        reasons.push({ score: 10, reason: "Location eligible" });
      } else {
        gaps.push({ score: 10, reason: "Location restriction" });
      }

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
      if (stage.includes(profile.business_age_band?.toLowerCase())) {
        score += 10;
        reasons.push({ score: 10, reason: "Business stage fit" });
      } else {
        gaps.push({ score: 10, reason: "Stage mismatch" });
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
      }

      // ---------------- USE OF FUNDS ---------------- (10)
      const needs = normalizeArray(profile.funding_needs);
      const uses = normalizeArray(program.use_of_funds);

      if (overlapScore(needs, uses) > 0) {
        score += 10;
        reasons.push({ score: 10, reason: "Funding purpose aligned" });
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
      }

      logger.info("Match Score: ", score)

      // ---------------- AI ----------------
      const openai = use_ai && Deno.env.get("OPENAI_API_KEY")
        ? new OpenAI({ apiKey: Deno.env.get("OPENAI_API_KEY") })
        : null;
      let aiScore = 0;
      let aiAnalysis = "";
      let aiConfidence = 0;

      if (openai && score >= 40) {
        try {
          const ai = await openai.responses.create({
            model: "gpt-4.1-mini",
            input: `Score match 0-100. Return JSON only.`,
          });

          const parsed = JSON.parse(ai.output_text || "{}");

          aiScore = parsed.score || 0;
          aiAnalysis = parsed.analysis || "";
          aiConfidence = parsed.confidence || 0.5;

          logger.info("AI Score: ", aiScore)
        } catch (e) {
          logger.error("AI failed", e);
        }
      }

      let finalScore = score;

      if(use_ai) {
        finalScore = Math.round(score * 0.7 + aiScore * 0.3);
      }

      logger.info("Match Reasons for " + business_id, reasons)
      logger.info("Gaps for " + business_id, gaps)
      logger.info("Final Score: ", finalScore)

      if (finalScore >= 40) {
        results.push({
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
        });

        saveMatchedProgram(results[results.length - 1], supabase);
      }

    }

    results.sort((a, b) => b.final_score - a.final_score);

    return new Response(JSON.stringify({ matches: results }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
    
  } catch (error) {
    logger.error("Error processing match-programs request", error);
    return new Response(
      JSON.stringify({ success: false, error: error.message || error }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        status: 500,
      }
    );
  }
})



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