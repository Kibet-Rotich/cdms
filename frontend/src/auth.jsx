import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { DEFAULT_PURPOSE, get, post, purpose, tokens } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    if (!tokens.get()) {
      setLoading(false);
      return;
    }
    try {
      const me = await get("/me");
      setUser(me);
      if (!purpose.get()) purpose.set(DEFAULT_PURPOSE[me.role]);
    } catch {
      tokens.clear();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMe();
  }, [loadMe]);

  const login = async (email, password) => {
    const res = await post("/auth/login", { email, password });
    tokens.set({ access: res.access, refresh: res.refresh });
    purpose.set(DEFAULT_PURPOSE[res.user.role]);
    const me = await get("/me");
    setUser(me);
    return me;
  };

  const logout = () => {
    tokens.clear();
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);

export const HOME_BY_ROLE = {
  PRESCRIBER: "/patients",
  PHARMACIST: "/patients",
  REGULATOR: "/dashboard",
  SYSTEM_ADMIN: "/admin/users",
  FACILITY_ADMIN: "/admin/users",
};
