import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import api from "./api";

const AuthCtx = createContext(null);

/**
 * Holds the authenticated session AND the initial bootstrap payload
 * (branches, settings, bookings) so the rest of the app renders with
 * zero additional round-trips on page load.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [branches, setBranches] = useState([]);
  const [settings, setSettings] = useState(null);
  const [initialBookings, setInitialBookings] = useState([]);
  const [loading, setLoading] = useState(true);

  const applyBootstrap = useCallback((data) => {
    // Normalizing role name mapping ("user" from DB corresponds to "staff" functionality)
    const normalizedUser = data.user ? {
      ...data.user,
      role: data.user.role === "user" ? "staff" : data.user.role
    } : null;

    setUser(normalizedUser);
    setBranches(data.branches || []);
    setSettings(data.settings || null);
    setInitialBookings(data.bookings || []);

    // Perform dynamic browser tab updates if matching setting entries exist
    if (data.settings) {
      document.title = "UD Catering";
      if (data.settings.favicon_url) {
        let link = document.querySelector("link[rel~='icon']");
        if (!link) {
          link = document.createElement("link");
          link.rel = "icon";
          document.head.appendChild(link);
        }
        link.href = data.settings.favicon_url;
      }
    }
  }, []);

  // On page refresh: validate token + load everything in a single request.
  useEffect(() => {
    const token = localStorage.getItem("ud_token");
    if (!token) { setLoading(false); return; }
    api.get("/bootstrap")
      .then((r) => applyBootstrap(r.data))
      .catch(() => { localStorage.removeItem("ud_token"); })
      .finally(() => setLoading(false));
  }, [applyBootstrap]);

  const login = async ({ username, password, role }) => {
    // Map client "staff" role label back to backend "user" role matching table column constraints
    const backendRole = role === "staff" ? "user" : role;
    const r = await api.post("/auth/login", { username, password, role: backendRole });
    localStorage.setItem("ud_token", r.data.token);
    
    // Immediately fetch bootstrap with the new token so the layout maps correctly
    const b = await api.get("/bootstrap");
    applyBootstrap(b.data);
    return b.data.user;
  };

  const logout = () => {
    localStorage.removeItem("ud_token");
    setUser(null); setBranches([]); setSettings(null); setInitialBookings([]);
  };

  const refreshLayout = useCallback(async () => {
    const [br, st] = await Promise.all([api.get("/branches"), api.get("/settings")]);
    setBranches(br.data); setSettings(st.data);
    return br.data;
  }, []);

  return (
    <AuthCtx.Provider value={{
      user, loading, login, logout,
      branches, settings, setSettings,
      initialBookings, setInitialBookings, refreshLayout,
    }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
