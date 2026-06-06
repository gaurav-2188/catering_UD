import React, { useEffect, useState } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import api from "./lib/api";
import { AuthProvider, useAuth } from "./lib/auth";
import LoginPage from "./pages/LoginPage";
import AppLayout from "./pages/AppLayout";
import BookingsPage from "./pages/BookingsPage";
import PreviousBookingsPage from "./pages/PreviousBookingsPage";
import MenuPage from "./pages/MenuPage";
import StaffPage from "./pages/StaffPage";
import BranchesPage from "./pages/BranchesPage";
import { BranchSettingsPage, AdminSettingsPage } from "./pages/SettingsPages";
import AnalyticsPage from "./pages/AnalyticsPage";

function AppShell() {
  const { user, loading } = useAuth();
  const [branches, setBranches] = useState([]);
  const [branchId, setBranchId] = useState(null);
  const [settings, setSettings] = useState(null);

  const loadAll = async () => {
    const [br, st] = await Promise.all([api.get("/branches"), api.get("/settings")]);
    setBranches(br.data); setSettings(st.data);
    return br.data;
  };

  useEffect(() => {
    if (!user) return;
    loadAll().then((br) => {
      if (user.role === "admin") setBranchId("all");
      else setBranchId(user.branch_id || br[0]?.id);
    });
  }, [user]);

  if (loading) return <div className="min-h-screen flex items-center justify-center text-[#5C6056]">Loading…</div>;
  if (!user) return <LoginPage />;
  if (!branches.length || !branchId) return <div className="min-h-screen flex items-center justify-center text-[#5C6056]">Setting up…</div>;

  const layoutProps = { branches, branchId, setBranchId, settings };

  return (
    <AppLayout {...layoutProps}>
      <Routes>
        <Route path="/" element={<BookingsPage branches={branches} branchId={branchId} settings={settings} />} />
        <Route path="/previous" element={<PreviousBookingsPage branches={branches} branchId={branchId} settings={settings} />} />
        {user.role !== "user" && <Route path="/menu" element={<MenuPage branches={branches} branchId={branchId} setBranchId={setBranchId} />} />}
        {user.role !== "user" && <Route path="/staff" element={<StaffPage branches={branches} />} />}
        {user.role === "manager" && <Route path="/branch-settings" element={<BranchSettingsPage branches={branches} reload={loadAll} />} />}
        {user.role === "admin" && <Route path="/branches" element={<BranchesPage branches={branches} reload={loadAll} />} />}
        {user.role === "admin" && <Route path="/admin-settings" element={<AdminSettingsPage settings={settings} setSettings={setSettings} branches={branches} reload={loadAll} />} />}
        {user.role === "admin" && <Route path="/analytics" element={<AnalyticsPage branches={branches} branchId={branchId} setBranchId={setBranchId} />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppLayout>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster position="top-right" richColors />
        <AppShell />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
