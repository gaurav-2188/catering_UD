import React, { createContext, useContext, useEffect, useState } from "react";
import api from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("ud_token");
    if (!token) { setLoading(false); return; }
    api.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => { localStorage.removeItem("ud_token"); })
      .finally(() => setLoading(false));
  }, []);

  const login = async ({ username, password, role }) => {
    const r = await api.post("/auth/login", { username, password, role });
    localStorage.setItem("ud_token", r.data.token);
    setUser(r.data.user);
    return r.data.user;
  };

  const logout = () => {
    localStorage.removeItem("ud_token");
    setUser(null);
  };

  return <AuthCtx.Provider value={{ user, loading, login, logout, setUser }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
