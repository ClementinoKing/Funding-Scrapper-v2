/**
 * 
 * Test body:
 * {  "batch_size": 5, "use_ai": false, "priority_threshold": 1}
 * 
 */

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.38.0";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const logger = {
  info: (msg: string, data?: unknown) => console.log("[INFO]", msg, data || ""),
  error: (msg: string, err?: unknown) => console.error("[ERROR]", msg, err || ""),
};

logger.info('server started');

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  
  try {
    const supabaseAdmin = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const { batch_size = 5, use_ai = false, priority_threshold = 1 } = await req.json();

    // Get pending matches that need processing
    const { data: pendingMatches, error: pendingError } = await supabaseAdmin
      .from("pending_program_matches")
      .select("id, business_id, priority")
      .eq("needs_matching", true)
      .gte("priority", priority_threshold)
      .order("priority", { ascending: false })
      .order("updated_at", { ascending: true })
      .limit(batch_size);

    if (pendingError) {
      throw pendingError;
    }

    logger.info("Pending Matches: ", pendingMatches) 

    if (!pendingMatches || pendingMatches.length === 0) {
      return new Response(
        JSON.stringify({
          success: true,
          processed: 0,
          message: "No pending matches found",
        }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

     const results = [];

    // Process each pending match
    for (const match of pendingMatches) {
      try {
        // Call the match-programs function
        const { data: matchResult, error } = await supabaseAdmin.functions.invoke("match-programs", {
          body: {
            business_id: match.business_id,
            use_ai: use_ai,
          },
        });

        if (error) {
          logger.error("Invoke error:", error);
        }

        // Update pending matches table
        // await supabaseAdmin
        //   .from("pending_program_matches")
        //   .update({
        //     needs_matching: false,
        //     last_matched_at: new Date().toISOString(),
        //     updated_at: new Date().toISOString(),
        //   })
        //   .eq("id", match.id);

        results.push({
          business_id: match.business_id,
          success: !error,
          matched_programs: matchResult?.matched_programs || 0,
          match_score_avg: matchResult?.average_score,
        });

        logger.info(`Processed business ${match.business_id}:`, matchResult);

        // Small delay between requests to avoid rate limiting
        await new Promise(resolve => setTimeout(resolve, 500));

      } catch (error) {
        logger.error(`Error processing business ${match.business_id}:`, error);
        results.push({
          business_id: match.business_id,
          success: false,
          error: error.message,
        });
      }
    }

    return new Response(
      JSON.stringify({
        success: true,
        processed: pendingMatches.length,
        results,
        timestamp: new Date().toISOString(),
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );

  } catch (error) {
    console.error("Background matcher error:", error);
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
})

/* To invoke locally:

  1. Run `supabase start` (see: https://supabase.com/docs/reference/cli/supabase-start)
  2. Make an HTTP request:

  curl -i --location --request POST 'http://127.0.0.1:54321/functions/v1/background-matcher' \
    --header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0' \
    --header 'Content-Type: application/json' \
    --data '{"name":"Functions"}'

*/
