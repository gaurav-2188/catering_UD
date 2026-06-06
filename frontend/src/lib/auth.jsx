import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import api from "./api";

// 1. Explicitly create and export the AuthCtx context object
export const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [branches, setBranches] = useState([]);
  const [settings, setSettings] = useState(null);
  const [initialBookings, setInitialBookings] = useState([]);
  const [loading, setLoading] = useState(true);

  const applyBootstrap = useCallback((data) => {
    // Normalizing role name mapping (DB 'user' maps to UI 'staff' context)
    const normalizedUser = data.user ? {
      ...data.user,
      role: data.user.role === "user" ? "staff" : data.user.role
    } : null;

    setUser(normalizedUser);
    setBranches(data.branches || []);
    setSettings(data.settings || null);
    setInitialBookings(data.bookings || []);

    // Brand Optimizations: Update browser title and load favicon from settings dynamically
    if (data.settings) {
      document.title = "UD Catering";
      
      const faviconUrl = Array.isArray(data.settings) 
        ? data.settings.find(s => s.key === 'favicon_url')?.value 
        : data.settings.favicon_url;

      if (faviconUrl) {
        let link = document.querySelector("link[rel~='icon']");
        if (!link) {
          link = document.createElement("link");
          link.rel = "icon";
          document.head.appendChild(link);
        }
        link.href = faviconUrl;
      }
    }
  }, []);

  // Check storage and load app data on page refresh
  useEffect(() => {
    const token = localStorage.getItem("ud_token");
    if (!token) { 
      setLoading(false); 
      return; 
    }
    api.get("/bootstrap")
      .then((r) => applyBootstrap(r.data))
      .catch(() => { 
        localStorage.removeItem("ud_token"); 
      })
      .finally(() => setLoading(false));
  }, [applyBootstrap]);

  const login = async ({ username, password, role }) => {
    const backendRole = role === "staff" ? "user" : role;
    const r = await api.post("/auth/login", { username, password, role: backendRole });
    localStorage.setItem("ud_token", r.data.token);
    
    const b = await api.get("/bootstrap");
    applyBootstrap(b.data);
    return b.data.user;
  };

  const logout = () => {
    localStorage.removeItem("ud_token");
    setUser(null); 
    setBranches([]); 
    setSettings(null); 
    setInitialBookings([]);
  };

  const refreshLayout = useCallback(async () => {
    const [br, st] = await Promise.all([api.get("/branches"), api.get("/settings")]);
    setBranches(br.data); 
    setSettings(st.data);
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

// 2. Add a default export to prevent import mix-ups in AppProvider trees
export default AuthProvider;
