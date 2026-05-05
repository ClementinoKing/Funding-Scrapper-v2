import { supabase } from './supabase'

/**
 * Enqueue job for matching for a business
 */
export async function triggerBusinessMatching(
  businessId: string,
  useAI = false
) {
  const { data, error } = await supabase.rpc(
    "enqueue_program_matching_job",
    {
      business_id: businessId,
      use_ai: useAI,
    }
  );

  if (error) {
    console.error("QUEUE INSERT FAILED:", error);
    return { success: false, error };
  }

  return { success: true, message_id: data };
}

/**
 * Manually trigger edge function for matching for a business
 */
export async function triggerEdgeBusinessMatching(
  businessId: string,
  useAI = true
) {
  try {
    // STEP 1: Insert into queue
    const { data: upsertData, error: upsertError } = await supabase
      .from("pending_program_matches")
      .upsert(
        {
          business_id: businessId,
          needs_matching: true,
          priority: 3,
          updated_at: new Date().toISOString(),
        },
        {
          onConflict: "business_id",
        }
      )
      .select()
      .single();

    if (upsertError) {
      console.error("UPSERT FAILED:", upsertError);
      return { success: false, error: upsertError };
    }

    console.log("UPSERT SUCCESS:", upsertData);

    // STEP 2: Trigger background matcher
    const { data, error } = await supabase.functions.invoke(
      "background-matcher",
      {
        body: {
          batch_size: 1,
          use_ai: useAI,
          priority_threshold: 3,
        },
      }
    );

    if (error) {
      console.error("FUNCTION INVOKE FAILED:", error);
      return { success: false, error };
    }

    return { success: true, data };
  } catch (error) {
    console.error("TRIGGER ERROR:", error);
    return { success: false, error };
  }
}

/**
 * Check if a business has pending matches
 */
export async function checkPendingMatches(businessId: string) {
  const { data, error } = await supabase
    .from("pending_program_matches")
    .select("*")
    .eq("business_id", businessId)
    .eq("needs_matching", true)
    .maybeSingle();

  return {
    hasPending: !!data && !error,
    data,
    error,
  };
}

/**
 * Get match results for a business
 */
export async function getBusinessMatches(businessId: string) {
  const { data, error } = await supabase
    .from('v_matched_programs')
    .select('*')
    .eq('business_id', businessId)
    .order('final_score', { ascending: false });

  return { data, error };
}

/**
 * Get match results for a business
 */
export async function getBusinessMatch(businessId: string, programSlug: string) {
  const { data, error } = await supabase
    .from('v_matched_programs')
    .select('*')
    .eq('business_id', businessId)
    .eq('program_slug', programSlug);

  return { data: data ? data?.[0] : null, error };
}