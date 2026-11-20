import { useCallback, useEffect, useMemo, useState } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "../lib/api";
import { AuthContext } from "./contexts";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(() => !getToken());

  const clear = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(clear);
    if (!getToken()) return;
    api
      .get("/users/me")
      .then(setUser)
      .catch(clear)
      .finally(() => setReady(true));
  }, [clear]);

  /** Store a sign-in response ({access_token, user}) from /auth/login or /auth/verify-email. */
  const startSession = useCallback((res) => {
    setToken(res.access_token);
    setUser(res.user);
    return res.user;
  }, []);

  const login = useCallback(async (email, password) => startSession(await api.post("/auth/login", { email, password })), [startSession]);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      /* token may already be invalid */
    }
    clear();
  }, [clear]);

  const refresh = useCallback(async () => setUser(await api.get("/users/me")), []);

  const value = useMemo(() => ({ user, ready, login, startSession, logout, refresh }), [user, ready, login, startSession, logout, refresh]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
