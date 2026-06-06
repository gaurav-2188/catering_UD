import React, { useState } from "react";
import { useAuth } from "../lib/auth";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { ChefHat, User, Shield, Briefcase } from "lucide-react";

const ROLES = [
  { key: "user", label: "Staff", icon: User, hint: "staff1 / staff123" },
  { key: "manager", label: "Manager", icon: Briefcase, hint: "manager1 / manager123" },
  { key: "admin", label: "Admin", icon: Shield, hint: "admin@udcatering.com / admin123" },
];

export default function LoginPage() {
  const { login } = useAuth();
  const [role, setRole] = useState("user");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login({ username: username.trim().toLowerCase(), password, role });
      toast.success("Welcome back!");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Invalid credentials");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F9F8F6] p-6" data-testid="login-page">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="h-11 w-11 rounded-2xl bg-[#4A5D23] text-white flex items-center justify-center">
            <ChefHat className="h-6 w-6" />
          </div>
          <div className="text-left">
            <div className="text-[11px] tracking-[0.25em] uppercase text-[#8A8D84]">UD Catering</div>
            <div className="font-display text-lg font-semibold text-[#1A1C18]">Operations Console</div>
          </div>
        </div>
        <div>
          <div className="bg-white rounded-2xl p-8 shadow-soft border border-[#E5E0D8]">
            <div className="eyebrow text-[#8A8D84] mb-2">Sign in</div>
            <h2 className="font-display text-2xl font-semibold mb-6">Choose your role to continue</h2>

            <Tabs value={role} onValueChange={setRole} className="w-full">
              <TabsList className="grid grid-cols-3 w-full bg-[#F2EFE9] p-1 rounded-xl h-auto">
                {ROLES.map((r) => (
                  <TabsTrigger
                    key={r.key}
                    value={r.key}
                    data-testid={`login-tab-${r.key}`}
                    className="data-[state=active]:bg-white data-[state=active]:text-[#4A5D23] data-[state=active]:shadow-sm rounded-lg py-2.5 font-medium"
                  >
                    <r.icon className="h-4 w-4 mr-1.5" />
                    {r.label}
                  </TabsTrigger>
                ))}
              </TabsList>

              {ROLES.map((r) => (
                <TabsContent key={r.key} value={r.key} className="mt-6">
                  <form onSubmit={submit} className="space-y-4">
                    <div>
                      <Label className="text-sm">Username</Label>
                      <Input
                        data-testid={`login-username-${r.key}`}
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder={r.key === "admin" ? "admin@udcatering.com" : `e.g. ${r.key}1`}
                        className="h-12 rounded-xl mt-1.5"
                        autoComplete="username"
                        required
                      />
                    </div>
                    <div>
                      <Label className="text-sm">Password</Label>
                      <Input
                        data-testid={`login-password-${r.key}`}
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        className="h-12 rounded-xl mt-1.5"
                        autoComplete="current-password"
                        required
                      />
                    </div>
                    <Button
                      data-testid={`login-submit-${r.key}`}
                      type="submit"
                      disabled={busy}
                      className="w-full h-12 rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white font-medium"
                    >
                      {busy ? "Signing in..." : `Sign in as ${r.label}`}
                    </Button>
                    <p className="text-xs text-[#8A8D84] text-center pt-1">
                      Demo: <span className="font-medium text-[#5C6056]">{r.hint}</span>
                    </p>
                  </form>
                </TabsContent>
              ))}
            </Tabs>
          </div>
        </div>
        <p className="text-center mt-6 text-xs text-[#8A8D84]">© UD Catering — Operations Console</p>
      </div>
    </div>
  );
}
