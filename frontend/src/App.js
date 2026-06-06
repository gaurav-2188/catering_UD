import React, { useEffect, useState } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
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
  const { user, loading, branches, settings, setSettings, initialBookings, refreshLayout } = useAuth();
  const [branchId, setBranchId] = useState(null);

  useEffect(() => {
    if (!user) { setBranchId(null); return; }
    setBranchId(user.role === "admin" ? "all" : (user.branch_id || branches[0]?.id || null));
  }, [user, branches]);

  if (loading) return <div className="min-h-screen flex items-center justify-center text-[#5C6056]">Loading…</div>;
  if (!user) return <LoginPage />;
  if (!branches.length || !branchId) return <div className="min-h-screen flex items-center justify-center text-[#5C6056]">Setting up…</div>;

  const layoutProps = { branches, branchId, setBranchId, settings };

  return (
    <AppLayout {...layoutProps}>
      <Routes>
        <Route path="/" element={<BookingsPage branches={branches} branchId={branchId} settings={settings} initialBookings={initialBookings} />} />
        <Route path="/previous" element={<PreviousBookingsPage branches={branches} branchId={branchId} settings={settings} initialBookings={initialBookings} />} />
        {user.role !== "user" && <Route path="/menu" element={<MenuPage branches={branches} branchId={branchId} setBranchId={setBranchId} />} />}
        {user.role !== "user" && <Route path="/staff" element={<StaffPage branches={branches} />} />}
        {user.role === "manager" && <Route path="/branch-settings" element={<BranchSettingsPage branches={branches} reload={refreshLayout} />} />}
        {user.role === "admin" && <Route path="/branches" element={<BranchesPage branches={branches} reload={refreshLayout} />} />}
        {user.role === "admin" && <Route path="/admin-settings" element={<AdminSettingsPage settings={settings} setSettings={setSettings} branches={branches} reload={refreshLayout} />} />}
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
