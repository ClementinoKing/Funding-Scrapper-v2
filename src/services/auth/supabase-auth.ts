import type { Role } from "@/types/domain";
import {supabase} from "@/lib/supabase";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL?.trim();
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim();

export interface SupabaseSessionUser {
  id: string;
  email: string;
  fullName: string;
  role: Role;
}

export interface SupabaseSession {
  user: SupabaseSessionUser;
  accessToken: string;
  refreshToken?: string;
}

interface SupabaseRefreshResponse {
  access_token: string;
  refresh_token?: string;
  user: SupabaseAuthUser;
}

interface SupabaseAuthUser {
  id: string;
  email?: string;
  user_metadata?: Record<string, unknown>;
}

interface SupabaseAuthResponse {
  access_token: string;
  refresh_token?: string;
  user: SupabaseAuthUser;
}

interface ProfileRow {
  id: string;
  email?: string | null;
  full_name?: string | null;
  role?: Role | string | null;
}

const ensureConfigured = () => {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    throw new Error("Supabase environment variables are not configured.");
  }
};

const profileHeaders = (accessToken: string) => ({
  apikey: SUPABASE_ANON_KEY ?? "",
  Authorization: `Bearer ${accessToken}`
});

const authHeaders = {
  "Content-Type": "application/json",
  apikey: SUPABASE_ANON_KEY ?? "",
  Authorization: `Bearer ${SUPABASE_ANON_KEY ?? ""}`
};

const fetchProfile = async (userId: string, accessToken: string): Promise<SupabaseSessionUser> => {
  ensureConfigured();
  const response = await fetch(
    `${SUPABASE_URL}/rest/v1/users?id=eq.${encodeURIComponent(userId)}&select=id,email,full_name,role`,
    { headers: profileHeaders(accessToken) }
  );
  if (!response.ok) {
    throw new Error(`Failed to load profile (${response.status})`);
  }
  const rows = (await response.json()) as ProfileRow[];
  const row = rows[0];
  return {
    id: row?.id ?? userId,
    email: row?.email?.trim() || "unknown@example.com",
    fullName: row?.full_name?.trim() || row?.email?.trim() || "Signed in user",
    role: row?.role === "admin" ? "admin" : "applicant"
  };
};

export const signInWithSupabase = async (email: string, password: string): Promise<SupabaseSession> => {
  ensureConfigured();
  const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: authHeaders,
    body: JSON.stringify({ email, password })
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Unable to sign in.");
  }
  const payload = (await response.json()) as SupabaseAuthResponse;
  const user = await fetchProfile(payload.user.id, payload.access_token);

  await supabase.auth.signInWithPassword({
    email,
    password,
  });

  return {
    user,
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token
  };
};

export const signUpWithSupabase = async (
  email: string,
  password: string,
  fullName: string
): Promise<SupabaseSession | null> => {
  ensureConfigured();
  const response = await fetch(`${SUPABASE_URL}/auth/v1/signup`, {
    method: "POST",
    headers: authHeaders,
    body: JSON.stringify({
      email,
      password,
      data: {
        full_name: fullName,
        role: "applicant"
      }
    })
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Unable to create account.");
  }

  const payload = (await response.json()) as Partial<SupabaseAuthResponse>;
  if (!payload.user || !payload.access_token) {
    return null;
  }

  const user = await fetchProfile(payload.user.id, payload.access_token);

  await supabase.auth.signInWithPassword({
    email,
    password,
  });
  
  return {
    user,
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token
  };
};

export const refreshSupabaseSession = async (refreshToken: string): Promise<SupabaseSession> => {
  ensureConfigured();
  const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
    method: "POST",
    headers: authHeaders,
    body: JSON.stringify({ refresh_token: refreshToken })
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Unable to refresh session.");
  }

  const payload = (await response.json()) as SupabaseRefreshResponse;
  const user = await fetchProfile(payload.user.id, payload.access_token);
  return {
    user,
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token
  };
};
