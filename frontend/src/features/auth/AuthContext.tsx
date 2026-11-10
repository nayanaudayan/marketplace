import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { setAuthFailureHandler, tokens } from "@/api/client";
import { authApi } from "@/api/endpoints";
import type { AuthResponse, Role, User } from "@/types";

export class WrongPortalError extends Error {
  role: Role;
  constructor(role: Role) {
    super("wrong portal");
    this.role = role;
  }
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  /** If allowedRoles is given and the account's role isn't in it, rejects with WrongPortalError and stores nothing. */
  login: (email: string, password: string, allowedRoles?: Role[]) => Promise<User>;
  register: (b: { name: string; email: string; password: string; phone?: string; role: "customer" | "seller" }) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(() => !!tokens.access || !!tokens.refresh);
  const qc = useQueryClient();

  const clearSession = useCallback(() => {
    tokens.clear();
    setUser(null);
    qc.clear();
  }, [qc]);

  useEffect(() => {
    setAuthFailureHandler(clearSession);
  }, [clearSession]);

  useEffect(() => {
    if (!tokens.access && !tokens.refresh) return;
    authApi
      .me()
      .then(setUser)
      .catch(() => clearSession())
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const applyAuth = useCallback(
    (res: AuthResponse) => {
      qc.clear();
      tokens.set(res);
      setUser(res.user);
      return res.user;
    },
    [qc],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      login: async (email, password, allowedRoles) => {
        const res = await authApi.login({ email, password });
        if (allowedRoles && !allowedRoles.includes(res.user.role)) {
          // Wrong portal for this account: never keep the session, and revoke the token that was just issued.
          authApi.logout(res.refresh_token).catch(() => undefined);
          throw new WrongPortalError(res.user.role);
        }
        return applyAuth(res);
      },
      register: async (b) => applyAuth(await authApi.register(b)),
      logout: async () => {
        const refresh = tokens.refresh;
        try {
          if (refresh) await authApi.logout(refresh);
        } catch {
          /* ignore: session is cleared locally regardless */
        }
        clearSession();
      },
      refreshUser: async () => setUser(await authApi.me()),
    }),
    [user, loading, applyAuth, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
