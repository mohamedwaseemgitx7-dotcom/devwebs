import { useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, refreshSession, setAccessToken, subscribeSession } from "../api/client";
import type { TokenResponse, User } from "../api/types";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: User | null;
  status: Status;
  login: (email: string, password: string) => Promise<User>;
  signup: (name: string, email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const queryClient = useQueryClient();

  const applySession = useCallback((session: TokenResponse | null) => {
    setAccessToken(session?.access_token ?? null);
    setUser(session?.user ?? null);
    setStatus(session ? "authenticated" : "anonymous");
  }, []);

  useEffect(() => {
    subscribeSession(applySession);
    // Restore the session from the HttpOnly refresh cookie on page load.
    refreshSession().then((session) => applySession(session));
  }, [applySession]);

  const login = useCallback(
    async (email: string, password: string) => {
      const session = await api<TokenResponse>("/auth/login", { method: "POST", body: { email, password } });
      applySession(session);
      queryClient.invalidateQueries();
      return session.user;
    },
    [applySession, queryClient],
  );

  const signup = useCallback(
    async (name: string, email: string, password: string) => {
      const session = await api<TokenResponse>("/auth/signup", { method: "POST", body: { name, email, password } });
      applySession(session);
      queryClient.invalidateQueries();
      return session.user;
    },
    [applySession, queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      applySession(null);
      queryClient.clear();
    }
  }, [applySession, queryClient]);

  const value = useMemo(() => ({ user, status, login, signup, logout }), [user, status, login, signup, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
