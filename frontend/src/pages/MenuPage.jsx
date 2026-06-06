import React, { useEffect, useState } from "react";
import api, { currency } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Plus, Trash2, Pencil } from "lucide-react";
import { toast } from "sonner";

export default function MenuPage({ branches, branchId, setBranchId }) {
  const { user } = useAuth();
  const effective = user.role === "admin" ? (branchId !== "all" ? branchId : branches[0]?.id) : user.branch_id;
  const [cats, setCats] = useState([]);
  const [items, setItems] = useState([]);
  const [catName, setCatName] = useState("");
  const [editItem, setEditItem] = useState(null);
  const [newCatId, setNewCatId] = useState("");

  const load = async () => {
    if (!effective) return;
    const [c, m] = await Promise.all([
      api.get("/categories", { params: { branch_id: effective } }),
      api.get("/menu-items", { params: { branch_id: effective } }),
    ]);
    setCats(c.data); setItems(m.data);
    if (!newCatId && c.data[0]) setNewCatId(c.data[0].id);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [effective]);

  const addCat = async () => {
    if (!catName.trim()) return;
    await api.post("/categories", { branch_id: effective, name: catName.trim(), sort_order: cats.length });
    setCatName(""); load(); toast.success("Category added");
  };
  const delCat = async (id) => {
    if (!window.confirm("Delete this category and all its items?")) return;
    await api.delete(`/categories/${id}`); load(); toast.success("Deleted");
  };
  const delItem = async (id) => {
    if (!window.confirm("Delete this menu item?")) return;
    await api.delete(`/menu-items/${id}`); load(); toast.success("Deleted");
  };
  const saveItem = async (data) => {
    if (data.id) await api.patch(`/menu-items/${data.id}`, { branch_id: effective, ...data });
    else await api.post("/menu-items", { branch_id: effective, category_id: newCatId, ...data });
    setEditItem(null); load(); toast.success("Saved");
  };

  return (
    <div data-testid="menu-page">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <div className="overline text-[#8A8D84]">Menu management</div>
          <h1 className="font-display text-3xl font-semibold">Menu & pricing</h1>
        </div>
        {user.role === "admin" && (
          <Select value={effective} onValueChange={setBranchId}>
            <SelectTrigger className="h-10 rounded-xl w-64" data-testid="menu-branch"><SelectValue /></SelectTrigger>
            <SelectContent>{branches.map((b) => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
          </Select>
        )}
      </div>

      <div className="grid lg:grid-cols-3 gap-5">
        <div className="bg-white rounded-2xl border border-[#E5E0D8] shadow-soft p-5">
          <div className="overline text-[#8A8D84] mb-3">Categories</div>
          <div className="space-y-1 mb-3">
            {cats.map((c) => (
              <div key={c.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-[#F2EFE9]" data-testid={`cat-${c.id}`}>
                <span className="text-sm font-medium">{c.name}</span>
                <Button size="icon" variant="ghost" className="h-7 w-7 text-[#B33A3A]" onClick={() => delCat(c.id)}><Trash2 className="h-3.5 w-3.5" /></Button>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Input data-testid="new-cat-name" value={catName} onChange={(e) => setCatName(e.target.value)} placeholder="New category" className="h-10 rounded-xl" />
            <Button data-testid="add-cat-btn" onClick={addCat} className="h-10 rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white">Add</Button>
          </div>
        </div>

        <div className="lg:col-span-2 bg-white rounded-2xl border border-[#E5E0D8] shadow-soft p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="overline text-[#8A8D84]">Menu items</div>
            <Button data-testid="new-item-btn" disabled={!cats.length}
              onClick={() => setEditItem({ name: "", price: 0, category_id: cats[0]?.id })}
              className="h-9 rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white"><Plus className="h-4 w-4 mr-1" /> New item</Button>
          </div>
          {cats.map((c) => {
            const ci = items.filter((i) => i.category_id === c.id);
            if (!ci.length) return null;
            return (
              <div key={c.id} className="mb-4">
                <div className="overline text-[#5C6056] mb-1.5">{c.name}</div>
                <div className="divide-y divide-[#E5E0D8] border border-[#E5E0D8] rounded-xl">
                  {ci.map((it) => (
                    <div key={it.id} className="flex items-center justify-between p-3 hover:bg-[#F2EFE9]">
                      <span className="text-sm">{it.name}</span>
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium">{currency(it.price)}</span>
                        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setEditItem(it)}><Pencil className="h-3.5 w-3.5" /></Button>
                        <Button size="icon" variant="ghost" className="h-7 w-7 text-[#B33A3A]" onClick={() => delItem(it.id)}><Trash2 className="h-3.5 w-3.5" /></Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
          {!items.length && <p className="text-sm text-[#8A8D84] text-center py-8">No items yet.</p>}
        </div>
      </div>

      <Dialog open={!!editItem} onOpenChange={(o) => !o && setEditItem(null)}>
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader><DialogTitle className="font-display text-xl">{editItem?.id ? "Edit" : "New"} menu item</DialogTitle></DialogHeader>
          {editItem && (
            <div className="space-y-3">
              <div>
                <Label>Category</Label>
                <Select value={editItem.category_id} onValueChange={(v) => setEditItem({ ...editItem, category_id: v })}>
                  <SelectTrigger className="h-11 rounded-xl mt-1.5"><SelectValue /></SelectTrigger>
                  <SelectContent>{cats.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div><Label>Name</Label><Input data-testid="item-name" className="h-11 rounded-xl mt-1.5" value={editItem.name} onChange={(e) => setEditItem({ ...editItem, name: e.target.value })} /></div>
              <div><Label>Price (₹)</Label><Input data-testid="item-price" type="number" min={0} className="h-11 rounded-xl mt-1.5" value={editItem.price} onChange={(e) => setEditItem({ ...editItem, price: Number(e.target.value) })} /></div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" className="rounded-xl" onClick={() => setEditItem(null)}>Cancel</Button>
                <Button data-testid="save-item-btn" className="rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white"
                  onClick={() => saveItem({ id: editItem.id, name: editItem.name, price: editItem.price, category_id: editItem.category_id })}>Save</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
