import { create } from "zustand";
import type { Role } from "@/types/domain";

interface SessionUser {
  id: string;
  name: string;
  email: string;
  role: Role;
}

interface AuthState {
  user: SessionUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  setSession: (session: { user: SessionUser; accessToken: string; refreshToken?: string | null }) => void;
  loginAs: (role: Role) => void;
  logout: () => void;
}

const STORAGE_KEY = "fundmatch.session";

const loadStoredSession = (): { user: SessionUser; accessToken: string } | null => {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as { user?: SessionUser; accessToken?: string };
    if (!parsed.user || !parsed.accessToken) {
      return null;
    }
    return { user: parsed.user, accessToken: parsed.accessToken };
  } catch {
    return null;
  }
};

const persistSession = (session: { user: SessionUser; accessToken: string } | null) => {
  if (typeof window === "undefined") {
    return;
  }
  if (!session) {
    window.localStorage.removeItem(STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
};

const initialSession = loadStoredSession();

export const useAuthStore = create<AuthState>((set) => ({
  user: initialSession?.user ?? null,
  accessToken: initialSession?.accessToken ?? null,
  isAuthenticated: Boolean(initialSession?.user),
  setSession: ({ user, accessToken }) => {
    persistSession({ user, accessToken });
    set({
      user,
      accessToken,
      isAuthenticated: true
    });
  },
  loginAs: (role) => {
    const user: SessionUser = {
      id: role === "admin" ? "admin_01" : "user_001",
      name: role === "admin" ? "Platform Admin" : "Clementino King",
      email: role === "admin" ? "admin@fundmatch.io" : "clementino@example.com",
      role
    };
    persistSession({ user, accessToken: "local-dev-token" });
    set({
      user,
      accessToken: "local-dev-token",
      isAuthenticated: true
    });
  },
  logout: () => {
    persistSession(null);
    set({ user: null, accessToken: null, isAuthenticated: false });
  }
}));
