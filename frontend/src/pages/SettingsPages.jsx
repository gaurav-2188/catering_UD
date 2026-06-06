import React, { useState } from "react";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Upload } from "lucide-react";

export function BranchSettingsPage({ branches, reload }) {
  const { user } = useAuth();
  const branch = branches.find((b) => b.id === user.branch_id);
  const [gst, setGst] = useState(branch?.gst_percent ?? 18);

  const save = async () => {
    if (!branch) return;
    await api.patch(`/branches/${branch.id}`, { gst_percent: Number(gst) });
    toast.success("GST updated"); reload();
  };
  if (!branch) return <p>No branch assigned.</p>;
  return (
    <div data-testid="branch-settings">
      <div className="eyebrow text-[#8A8D84]">Branch settings</div>
      <h1 className="font-display text-3xl font-semibold mb-6">{branch.name}</h1>
      <div className="bg-white rounded-2xl border border-[#E5E0D8] shadow-soft p-6 max-w-md">
        <Label>GST percent</Label>
        <Input data-testid="gst-input" type="number" min={0} max={100} value={gst} onChange={(e) => setGst(e.target.value)} className="h-12 rounded-xl mt-1.5" />
        <p className="text-xs text-[#8A8D84] mt-2">Applies to all new bookings at this branch.</p>
        <Button data-testid="save-gst-btn" className="mt-4 rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white" onClick={save}>Save</Button>
      </div>
    </div>
  );
}

export function AdminSettingsPage({ settings, setSettings, branches, reload }) {
  const [gstBranch, setGstBranch] = useState(branches[0]?.id);
  const [gst, setGst] = useState(branches[0]?.gst_percent ?? 18);

  const onFile = (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    if (f.size > 1024 * 1024) return toast.error("Logo must be under 1MB");
    const reader = new FileReader();
    reader.onload = async () => {
      const dataUrl = reader.result;
      const r = await api.patch("/settings", { id: "global", company_logo: dataUrl });
      setSettings(r.data); toast.success("Logo updated");
    };
    reader.readAsDataURL(f);
  };

  const saveGst = async () => {
    await api.patch(`/branches/${gstBranch}`, { gst_percent: Number(gst) });
    toast.success("GST updated"); reload();
  };

  React.useEffect(() => {
    const b = branches.find((x) => x.id === gstBranch);
    if (b) setGst(b.gst_percent);
  }, [gstBranch, branches]);

  return (
    <div data-testid="admin-settings">
      <div className="eyebrow text-[#8A8D84]">Admin settings</div>
      <h1 className="font-display text-3xl font-semibold mb-6">Global settings</h1>

      <div className="grid lg:grid-cols-2 gap-5">
        <div className="bg-white rounded-2xl border border-[#E5E0D8] shadow-soft p-6">
          <div className="eyebrow text-[#8A8D84] mb-3">Company logo</div>
          <div className="flex items-center gap-4 mb-4">
            {settings?.company_logo ? (
              <img src={settings.company_logo} alt="logo" className="h-20 w-20 rounded-xl object-cover border border-[#E5E0D8]" />
            ) : (
              <div className="h-20 w-20 rounded-xl bg-[#F2EFE9] flex items-center justify-center text-[#8A8D84]">No logo</div>
            )}
            <label className="cursor-pointer">
              <input data-testid="logo-upload" type="file" accept="image/*" className="hidden" onChange={onFile} />
              <span className="inline-flex items-center px-4 h-10 rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white text-sm font-medium">
                <Upload className="h-4 w-4 mr-1.5" /> Upload logo
              </span>
            </label>
          </div>
          <p className="text-xs text-[#8A8D84]">PNG/JPG up to 1MB. Shown in the header and on PDF invoices.</p>
        </div>

        <div className="bg-white rounded-2xl border border-[#E5E0D8] shadow-soft p-6">
          <div className="eyebrow text-[#8A8D84] mb-3">Per-branch GST</div>
          <div className="space-y-3">
            <div>
              <Label>Branch</Label>
              <Select value={gstBranch} onValueChange={setGstBranch}>
                <SelectTrigger className="h-11 rounded-xl mt-1.5"><SelectValue /></SelectTrigger>
                <SelectContent>{branches.map((b) => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label>GST percent</Label>
              <Input data-testid="admin-gst-input" type="number" value={gst} onChange={(e) => setGst(e.target.value)} className="h-11 rounded-xl mt-1.5" />
            </div>
            <Button data-testid="admin-save-gst-btn" className="rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white" onClick={saveGst}>Save GST</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
