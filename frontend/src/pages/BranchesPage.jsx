import React, { useState } from "react";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function BranchesPage({ branches, reload }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", address: "", gst_percent: 18 });
  const [editing, setEditing] = useState(null);

  const save = async () => {
    try {
      if (editing) await api.patch(`/branches/${editing.id}`, form);
      else await api.post("/branches", form);
      setOpen(false); setEditing(null); setForm({ name: "", address: "", gst_percent: 18 });
      reload(); toast.success("Saved");
    } catch (e) { toast.error("Failed"); }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this branch and its menu/bookings?")) return;
    await api.delete(`/branches/${id}`); reload(); toast.success("Deleted");
  };

  return (
    <div data-testid="branches-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="overline text-[#8A8D84]">Branches</div>
          <h1 className="font-display text-3xl font-semibold">Catering branches</h1>
        </div>
        <Button data-testid="new-branch-btn"
          onClick={() => { setEditing(null); setForm({ name: "", address: "", gst_percent: 18 }); setOpen(true); }}
          className="h-10 rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white"><Plus className="h-4 w-4 mr-1.5" />New branch</Button>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {branches.map((b) => (
          <div key={b.id} className="bg-white rounded-2xl border border-[#E5E0D8] shadow-soft p-5" data-testid={`branch-card-${b.id}`}>
            <div className="font-display text-lg font-semibold">{b.name}</div>
            <div className="text-sm text-[#5C6056] mt-1">{b.address || "—"}</div>
            <div className="text-xs text-[#8A8D84] mt-2">GST: {b.gst_percent}%</div>
            <div className="flex justify-end gap-2 mt-4">
              <Button variant="outline" className="rounded-xl h-9" onClick={() => { setEditing(b); setForm({ name: b.name, address: b.address, gst_percent: b.gst_percent }); setOpen(true); }}>Edit</Button>
              <Button variant="ghost" className="rounded-xl h-9 text-[#B33A3A]" onClick={() => del(b.id)}><Trash2 className="h-4 w-4" /></Button>
            </div>
          </div>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader><DialogTitle className="font-display text-xl">{editing ? "Edit" : "New"} branch</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Name</Label><Input data-testid="branch-name" className="h-11 rounded-xl mt-1.5" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div><Label>Address</Label><Input data-testid="branch-address" className="h-11 rounded-xl mt-1.5" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></div>
            <div><Label>GST percent</Label><Input data-testid="branch-gst" type="number" className="h-11 rounded-xl mt-1.5" value={form.gst_percent} onChange={(e) => setForm({ ...form, gst_percent: Number(e.target.value) })} /></div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" className="rounded-xl" onClick={() => setOpen(false)}>Cancel</Button>
              <Button data-testid="save-branch-btn" className="rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white" onClick={save}>Save</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
