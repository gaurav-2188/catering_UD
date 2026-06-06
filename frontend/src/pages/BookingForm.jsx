import React, { useEffect, useMemo, useState } from "react";
import api, { currency, computeTotals } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Plus, Minus, Trash2 } from "lucide-react";

export default function BookingForm({ branches, currentBranchId, initial, onCancel, onSubmit }) {
  const { user } = useAuth();
  const lockedBranch = user.role !== "admin" ? user.branch_id : null;
  const defaultBranch = initial?.branch_id || lockedBranch || currentBranchId || branches[0]?.id;

  const [branchId, setBranchId] = useState(defaultBranch);
  const [customer_name, setName] = useState(initial?.customer_name || "");
  const [phone, setPhone] = useState(initial?.phone || "");
  const [num_people, setNum] = useState(initial?.num_people || 50);
  const [venue_type, setVenueType] = useState(initial?.venue_type || "in_house");
  const [venue_address, setVenueAddr] = useState(initial?.venue_address || "");
  const [event_date, setDate] = useState(initial?.event_date || new Date().toISOString().slice(0, 10));
  const [event_time, setTime] = useState(initial?.event_time || "19:00");
  const [event_end_time, setEndTime] = useState(initial?.event_end_time || "22:00");
  const [discount_amount, setDiscAmt] = useState(initial?.discount_amount || 0);
  const [discount_percent, setDiscPct] = useState(initial?.discount_percent || 0);
  const [transportation_cost, setTransport] = useState(initial?.transportation_cost || 0);
  const [advance_paid, setAdvance] = useState(initial?.advance_paid || 0);
  const [notes, setNotes] = useState(initial?.notes || "");
  const [items, setItems] = useState(initial?.items || []);

  const [cats, setCats] = useState([]);
  const [menu, setMenu] = useState([]);

  useEffect(() => {
    if (!branchId) return;
    Promise.all([
      api.get("/categories", { params: { branch_id: branchId } }),
      api.get("/menu-items", { params: { branch_id: branchId } }),
    ]).then(([c, m]) => { setCats(c.data); setMenu(m.data); });
  }, [branchId]);

  const branch = branches.find((b) => b.id === branchId);
  const gst = branch?.gst_percent ?? 18;
  const totals = useMemo(
    () => computeTotals({ items, discount_amount, discount_percent, transportation_cost, advance_paid, gst_percent: gst }),
    [items, discount_amount, discount_percent, transportation_cost, advance_paid, gst]
  );

  const addItem = (mi) => {
    const ex = items.find((x) => x.item_id === mi.id);
    if (ex) setItems(items.map((x) => x.item_id === mi.id ? { ...x, quantity: x.quantity + 1 } : x));
    else setItems([...items, { item_id: mi.id, name: mi.name, price: mi.price, quantity: 1 }]);
  };
  const updateQty = (id, q) => {
    if (q <= 0) setItems(items.filter((x) => x.item_id !== id));
    else setItems(items.map((x) => x.item_id === id ? { ...x, quantity: q } : x));
  };

  const submit = (e) => {
    e.preventDefault();
    if (!items.length) return alert("Add at least one menu item.");
    if (event_end_time <= event_time) return alert("End time must be after start time.");
    onSubmit({
      branch_id: branchId, customer_name, phone, num_people: Number(num_people),
      venue_type, venue_address, event_date, event_time, event_end_time,
      items,
      discount_amount: Number(discount_amount), discount_percent: Number(discount_percent),
      transportation_cost: Number(transportation_cost), advance_paid: Number(advance_paid),
      notes,
    });
  };

  return (
    <form onSubmit={submit} className="space-y-6" data-testid="booking-form">
      {/* Branch + customer */}
      <Section title="Branch & customer">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {user.role === "admin" && (
            <div>
              <Label>Branch</Label>
              <Select value={branchId} onValueChange={setBranchId} disabled={!!initial}>
                <SelectTrigger className="h-12 rounded-xl mt-1.5" data-testid="form-branch">
                  <SelectValue /></SelectTrigger>
                <SelectContent>
                  {branches.map((b) => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}
          <Field label="Customer name"><Input data-testid="form-name" required value={customer_name} onChange={(e) => setName(e.target.value)} className="h-12 rounded-xl" /></Field>
          <Field label="Phone"><Input data-testid="form-phone" required value={phone} onChange={(e) => setPhone(e.target.value)} className="h-12 rounded-xl" /></Field>
          <Field label="Number of people"><Input data-testid="form-people" type="number" min={1} required value={num_people} onChange={(e) => setNum(e.target.value)} className="h-12 rounded-xl" /></Field>
        </div>
      </Section>

      {/* Venue */}
      <Section title="Venue & schedule">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <Label>Venue type</Label>
            <Select value={venue_type} onValueChange={setVenueType}>
              <SelectTrigger className="h-12 rounded-xl mt-1.5" data-testid="form-venue-type"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="in_house">In-house (Party Hall)</SelectItem>
                <SelectItem value="outside">Outside Catering</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Field label="Venue address"><Input data-testid="form-venue-address" value={venue_address} onChange={(e) => setVenueAddr(e.target.value)} placeholder={venue_type === "in_house" ? "Optional" : "Required for outside catering"} className="h-12 rounded-xl" /></Field>
          <Field label="Event date"><Input data-testid="form-date" type="date" required value={event_date} onChange={(e) => setDate(e.target.value)} className="h-12 rounded-xl" /></Field>
          <Field label="Start time"><Input data-testid="form-time" type="time" required value={event_time} onChange={(e) => setTime(e.target.value)} className="h-12 rounded-xl" /></Field>
          <Field label="End time"><Input data-testid="form-end-time" type="time" required value={event_end_time} onChange={(e) => setEndTime(e.target.value)} className="h-12 rounded-xl" /></Field>
        </div>
      </Section>

      {/* Menu */}
      <Section title="Menu selection">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-xl border border-[#E5E0D8] p-3 max-h-72 overflow-auto" data-testid="menu-picker">
            {cats.map((c) => {
              const cm = menu.filter((m) => m.category_id === c.id);
              if (!cm.length) return null;
              return (
                <div key={c.id} className="mb-3">
                  <div className="overline text-[#8A8D84] mb-1.5">{c.name}</div>
                  <div className="space-y-1">
                    {cm.map((mi) => (
                      <button type="button" key={mi.id} onClick={() => addItem(mi)}
                        data-testid={`menu-add-${mi.id}`}
                        className="w-full flex justify-between items-center p-2 rounded-lg hover:bg-[#F2EFE9] text-sm">
                        <span className="text-left">{mi.name}</span>
                        <span className="flex items-center gap-2">
                          <span className="text-[#5C6056]">{currency(mi.price)}</span>
                          <Plus className="h-3.5 w-3.5 text-[#4A5D23]" />
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
            {!cats.length && <p className="text-sm text-[#8A8D84] text-center py-6">No menu items yet — ask manager to add.</p>}
          </div>

          <div className="rounded-xl border border-[#E5E0D8] p-3 max-h-72 overflow-auto" data-testid="selected-items">
            {items.length === 0 && <p className="text-sm text-[#8A8D84] text-center py-6">Selected items appear here.</p>}
            {items.map((it) => (
              <div key={it.item_id} className="flex items-center gap-2 py-2 border-b last:border-0 border-[#E5E0D8]">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{it.name}</div>
                  <div className="text-xs text-[#8A8D84]">{currency(it.price)} each</div>
                </div>
                <div className="flex items-center gap-1">
                  <Button type="button" size="icon" variant="outline" className="h-8 w-8 rounded-lg" onClick={() => updateQty(it.item_id, it.quantity - 1)}><Minus className="h-3 w-3" /></Button>
                  <Input data-testid={`qty-${it.item_id}`} className="h-8 w-14 rounded-lg text-center" value={it.quantity} onChange={(e) => updateQty(it.item_id, Number(e.target.value) || 0)} />
                  <Button type="button" size="icon" variant="outline" className="h-8 w-8 rounded-lg" onClick={() => updateQty(it.item_id, it.quantity + 1)}><Plus className="h-3 w-3" /></Button>
                  <Button type="button" size="icon" variant="ghost" className="h-8 w-8 text-[#B33A3A]" onClick={() => updateQty(it.item_id, 0)}><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* Financials */}
      <Section title="Financials & notes">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <Field label="Discount (₹)"><Input data-testid="form-disc-amt" type="number" min={0} value={discount_amount} onChange={(e) => setDiscAmt(e.target.value)} className="h-12 rounded-xl" /></Field>
          <Field label="Discount (%)"><Input data-testid="form-disc-pct" type="number" min={0} max={100} value={discount_percent} onChange={(e) => setDiscPct(e.target.value)} className="h-12 rounded-xl" /></Field>
          <Field label="Transportation (₹)"><Input data-testid="form-transport" type="number" min={0} value={transportation_cost} onChange={(e) => setTransport(e.target.value)} className="h-12 rounded-xl" /></Field>
          <Field label="Advance paid (₹)"><Input data-testid="form-advance" type="number" min={0} value={advance_paid} onChange={(e) => setAdvance(e.target.value)} className="h-12 rounded-xl" /></Field>
        </div>
        <div className="mt-3">
          <Label>Cooking / Special instructions</Label>
          <Textarea data-testid="form-notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} className="rounded-xl mt-1.5" placeholder="Less spicy, jain options for 5 guests, etc." />
        </div>

        <div className="mt-4 rounded-xl bg-[#F9F8F6] border border-[#E5E0D8] p-4 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm" data-testid="totals-preview">
          <Stat label="Subtotal" value={currency(totals.subtotal)} />
          <Stat label={`GST (${gst}%)`} value={currency(totals.gst)} />
          <Stat label="Total" value={currency(totals.total)} />
          <Stat label="Balance due" value={currency(totals.due)} accent />
        </div>
      </Section>

      <div className="flex justify-end gap-2 sticky bottom-0 bg-white pt-3 border-t border-[#E5E0D8]">
        <Button type="button" variant="outline" className="h-11 rounded-xl" onClick={onCancel}>Cancel</Button>
        <Button data-testid="form-submit" type="submit" className="h-11 rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white px-6">
          {initial ? "Save changes" : "Create booking"}
        </Button>
      </div>
    </form>
  );
}

const Section = ({ title, children }) => (
  <div>
    <div className="overline text-[#8A8D84] mb-3">{title}</div>
    {children}
  </div>
);
const Field = ({ label, children }) => (
  <div><Label>{label}</Label><div className="mt-1.5">{children}</div></div>
);
const Stat = ({ label, value, accent }) => (
  <div>
    <div className="overline text-[#8A8D84]">{label}</div>
    <div className={`font-display text-base font-semibold ${accent ? "text-[#C84B31]" : "text-[#1A1C18]"}`}>{value}</div>
  </div>
);
