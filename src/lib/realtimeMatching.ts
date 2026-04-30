import { supabase } from './supabase'

/**
 * Subscribe to real-time updates for a business's matches
 */
export function subscribeToBusinessMatches(businessId: string, callback: (payload: unknown) => void) {
  console.log("Subscribing to channel", `business-matches-${businessId}`);
  const channel = supabase.channel(`business-matches-${businessId}`)
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'program_matches',
        filter: `business_id=eq.${businessId}`,
      },
      (payload) => {
        console.log('New match added:', payload.new);
        callback(payload.new);
      }
    )
    .on(
      'postgres_changes',
      {
        event: 'UPDATE',
        schema: 'public',
        table: 'pending_program_matches',
        filter: `business_id=eq.${businessId}`,
      },
      (payload) => {
        console.log("Subscription Result",payload);
        console.log('Pending match updated:', payload.new);
        if (!payload.new.needs_matching) {
          // Matching completed, trigger a refresh
          callback({ type: 'matching_completed', businessId });
        }
      }
    )
    .subscribe();

  return () => {
    console.log("Unsubscribing to channel", `business-matches-${businessId}`, channel);
    supabase.removeChannel(channel);
  };
}

/**
 * Subscribe to all business matches (admin view)
 */
export function subscribeToAllMatches(callback: (payload: unknown) => void) {
  console.log("Subscribing to channel", 'all-business-matches');
  const channel = supabase.channel('all-business-matches')
    .on(
      'postgres_changes',
      {
        event: '*',
        schema: 'public',
        table: 'program_matches',
      },
      (payload) => {
        console.log("Subscription Result",payload);
        callback(payload);
      }
    )
    .subscribe();

  return () => {
    console.log("Channel removed:", channel);
    supabase.removeChannel(channel);
  };
}