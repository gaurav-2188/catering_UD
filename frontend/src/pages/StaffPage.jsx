import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

const ROLE_LABEL = { admin: "Admin", manager: "Manager", user: "Staff" };

export default function StaffPage({ branches }) {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ username: "", password: "", role: "user", branch_id: branches[0]?.id });

  const load = async () => { const r = await api.get("/users"); setUsers(r.data); };
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.username || !form.password) return toast.error("Username & password required");
    try {
      await api.post("/users", { ...form, username: form.username.toLowerCase() });
      setOpen(false); setForm({ username: "", password: "", role: "user", branch_id: branches[0]?.id });
      load(); toast.success("Account created");
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this account?")) return;
    try { await api.delete(`/users/${id}`); load(); toast.success("Deleted"); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const branchName = (id) => branches.find((b) => b.id === id)?.name || "—";
  const availableRoles = user.role === "admin" ? ["admin", "manager", "user"] : ["user"];

  return (
    <div data-testid="staff-page">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <div className="eyebrow text-[#8A8D84]">{user.role === "admin" ? "User management" : "Staff management"}</div>
          <h1 className="font-display text-3xl font-semibold">{user.role === "admin" ? "All accounts" : "Staff accounts"}</h1>
        </div>
        <Button data-testid="new-user-btn" onClick={() => setOpen(true)} className="h-10 rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white">
          <Plus className="h-4 w-4 mr-1.5" /> New account
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-[#E5E0D8] shadow-soft overflow-hidden">
        <table className="w-full text-base">
          <thead className="bg-[#F9F8F6] text-[#5C6056]">
            <tr>
              <th className="text-left p-3 eyebrow">Username</th>
              <th className="text-left p-3 eyebrow">Role</th>
              <th className="text-left p-3 eyebrow">Branch</th>
              <th className="text-left p-3 eyebrow">Created</th>
              <th className="text-right p-3 eyebrow">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-[#E5E0D8] hover:bg-[#F2EFE9]">
                <td className="p-3 font-medium" data-testid={`user-${u.id}`}>{u.username}</td>
                <td className="p-3"><span className="text-xs px-2 py-0.5 rounded-full bg-[#F2EFE9]">{ROLE_LABEL[u.role]}</span></td>
                <td className="p-3 text-[#5C6056]">{u.branch_id ? branchName(u.branch_id) : "—"}</td>
                <td className="p-3 text-[#8A8D84]">{new Date(u.created_at).toLocaleDateString("en-IN")}</td>
                <td className="p-3 text-right">
                  <Button size="icon" variant="ghost" className="h-8 w-8 text-[#B33A3A]" onClick={() => del(u.id)}><Trash2 className="h-3.5 w-3.5" /></Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader><DialogTitle className="font-display text-xl">Create account</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Username</Label><Input data-testid="new-username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="h-11 rounded-xl mt-1.5" /></div>
            <div><Label>Password</Label><Input data-testid="new-password" type="text" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="h-11 rounded-xl mt-1.5" /></div>
            {user.role === "admin" && (
              <div>
                <Label>Role</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger className="h-11 rounded-xl mt-1.5" data-testid="new-role"><SelectValue /></SelectTrigger>
                  <SelectContent>{availableRoles.map((r) => <SelectItem key={r} value={r}>{ROLE_LABEL[r]}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            )}
            {form.role !== "admin" && user.role === "admin" && (
              <div>
                <Label>Branch</Label>
                <Select value={form.branch_id} onValueChange={(v) => setForm({ ...form, branch_id: v })}>
                  <SelectTrigger className="h-11 rounded-xl mt-1.5" data-testid="new-branch"><SelectValue /></SelectTrigger>
                  <SelectContent>{branches.map((b) => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" className="rounded-xl" onClick={() => setOpen(false)}>Cancel</Button>
              <Button data-testid="create-user-btn" className="rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white" onClick={create}>Create</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
