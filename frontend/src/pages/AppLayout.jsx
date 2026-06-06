import React from "react";
import { useAuth } from "../lib/auth";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Button } from "../components/ui/button";
import { Link, useLocation } from "react-router-dom";
import { ChefHat, LayoutDashboard, Settings, Users, Building2, ListTree, LogOut, BarChart3 } from "lucide-react";

export default function AppLayout({ children, branches, branchId, setBranchId, settings }) {
  const { user, logout } = useAuth();
  const loc = useLocation();

  const navByRole = {
    user: [{ to: "/", label: "Bookings", icon: LayoutDashboard }],
    manager: [
      { to: "/", label: "Bookings", icon: LayoutDashboard },
      { to: "/menu", label: "Menu", icon: ListTree },
      { to: "/staff", label: "Staff", icon: Users },
      { to: "/branch-settings", label: "Branch Settings", icon: Settings },
    ],
    admin: [
      { to: "/", label: "Bookings", icon: LayoutDashboard },
      { to: "/analytics", label: "Analytics", icon: BarChart3 },
      { to: "/menu", label: "Menu", icon: ListTree },
      { to: "/branches", label: "Branches", icon: Building2 },
      { to: "/staff", label: "All Users", icon: Users },
      { to: "/admin-settings", label: "Settings", icon: Settings },
    ],
  };
  const nav = navByRole[user.role] || [];

  return (
    <div className="min-h-screen bg-[#F9F8F6]" data-testid="app-layout">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-white border-b border-[#E5E0D8]">
        <div className="px-5 lg:px-8 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            {settings?.company_logo ? (
              <img src={settings.company_logo} alt="logo" className="h-9 w-9 rounded-xl object-cover" />
            ) : (
              <div className="h-9 w-9 rounded-xl bg-[#4A5D23] text-white flex items-center justify-center">
                <ChefHat className="h-5 w-5" />
              </div>
            )}
            <div className="min-w-0">
              <div className="font-display font-semibold text-base leading-tight truncate">UD Catering</div>
              <div className="text-[11px] text-[#8A8D84] capitalize">{user.role} console</div>
            </div>
          </div>
          <div className="flex items-center gap-2 lg:gap-3">
            <div className="hidden sm:block overline text-[#8A8D84]">Branch</div>
            <Select value={branchId || "all"} onValueChange={setBranchId}>
              <SelectTrigger data-testid="branch-selector" className="h-10 min-w-[220px] rounded-xl border-[#E5E0D8]">
                <SelectValue placeholder="Select branch" />
              </SelectTrigger>
              <SelectContent>
                {user.role === "admin" && <SelectItem value="all" data-testid="branch-option-all">All branches</SelectItem>}
                {branches.map((b) => (
                  <SelectItem key={b.id} value={b.id} data-testid={`branch-option-${b.id}`}>{b.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              data-testid="logout-btn"
              variant="ghost"
              onClick={logout}
              className="h-10 rounded-xl text-[#5C6056] hover:bg-[#F2EFE9]"
            >
              <LogOut className="h-4 w-4 mr-1.5" /> Sign out
            </Button>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className="hidden lg:flex flex-col w-60 shrink-0 border-r border-[#E5E0D8] bg-[#F9F8F6] min-h-[calc(100vh-4rem)] p-4">
          <div className="overline text-[#8A8D84] px-3 mb-3">Workspace</div>
          <nav className="space-y-1">
            {nav.map((n) => {
              const active = loc.pathname === n.to;
              return (
                <Link
                  key={n.to}
                  to={n.to}
                  data-testid={`nav-${n.label.toLowerCase().replace(/\s+/g,"-")}`}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                    active ? "bg-white text-[#4A5D23] shadow-soft border border-[#E5E0D8]" : "text-[#5C6056] hover:bg-[#F2EFE9]"
                  }`}
                >
                  <n.icon className="h-4 w-4" /> {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="mt-auto pt-6 px-3">
            <div className="overline text-[#8A8D84] mb-1">Signed in as</div>
            <div className="text-sm font-medium text-[#1A1C18] truncate">{user.username}</div>
            <div className="text-xs text-[#8A8D84] capitalize mt-0.5">{user.role}</div>
          </div>
        </aside>

        <main className="flex-1 min-w-0 p-5 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
