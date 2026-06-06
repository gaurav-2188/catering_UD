import React, { useEffect, useMemo, useState } from "react";
import api, { currency, computeTotals } from "../lib/api";
import { useAuth } from "../lib/auth";
import { supabase } from "../lib/supabase";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { generateInvoicePDF } from "../lib/pdf";
import { ChevronLeft, ChevronRight, Plus, FileText, CheckCircle2, XCircle, Pencil, AlertTriangle, MapPin, Users, Clock } from "lucide-react";
import BookingForm from "./BookingForm";
import { toast } from "sonner";

function monthMatrix(year, month) {
  const first = new Date(year, month, 1);
  const startWeekday = first.getDay(); // 0=Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));
  while (cells.length % 7) cells.push(null);
  return cells;
}
const fmtYMD = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export default function BookingsPage({ branches, branchId, settings }) {
  const { user } = useAuth();
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cursor, setCursor] = useState(() => { const n = new Date(); return new Date(n.getFullYear(), n.getMonth(), 1); });
  const [dayPanel, setDayPanel] = useState(null);
  const [openBooking, setOpenBooking] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [conflict, setConflict] = useState(null); // {existing_id, pendingPayload}

  const load = async () => {
    setLoading(true);
    try {
      const params = user.role === "admin" && branchId && branchId !== "all" ? { branch_id: branchId } : {};
      const r = await api.get("/bookings", { params });
      let list = r.data;
      if (user.role === "admin" && branchId === "all") {/* keep all */}
      else if (branchId && branchId !== "all") list = list.filter((b) => b.branch_id === branchId);
      setBookings(list);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [branchId]);

  // Realtime — subscribe to bookings changes so multiple staff see the same calendar live.
  useEffect(() => {
    if (!supabase) return;
    const filter = (user.role !== "admin" && user.branch_id)
      ? `branch_id=eq.${user.branch_id}`
      : undefined;
    const ch = supabase
      .channel(`bookings:${user.id}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "bookings", ...(filter ? { filter } : {}) }, () => load())
      .subscribe();
    return () => { supabase.removeChannel(ch); };
    /* eslint-disable-next-line */
  }, [user.id, user.role, user.branch_id]);

  const bookingsByDate = useMemo(() => {
    const m = {};
    bookings.forEach((b) => { (m[b.event_date] = m[b.event_date] || []).push(b); });
    Object.values(m).forEach((arr) => arr.sort((a, b) => a.event_time.localeCompare(b.event_time)));
    return m;
  }, [bookings]);

  const cells = monthMatrix(cursor.getFullYear(), cursor.getMonth());

  const submitBooking = async (payload, ignore_conflict = false) => {
    try {
      const final = { ...payload, ignore_conflict };
      if (editing) {
        await api.patch(`/bookings/${editing.id}`, final);
        toast.success("Booking updated");
      } else {
        await api.post("/bookings", final);
        toast.success("Booking created");
      }
      setFormOpen(false); setEditing(null); setConflict(null);
      load();
    } catch (e) {
      const det = e.response?.data?.detail;
      if (e.response?.status === 409 && det?.code === "TIME_CONFLICT") {
        setConflict({ existing_id: det.existing_id, pendingPayload: payload });
      } else {
        toast.error(typeof det === "string" ? det : "Failed to save booking");
      }
    }
  };

  const markStatus = async (bk, status) => {
    try {
      await api.patch(`/bookings/${bk.id}`, { status });
      toast.success(`Marked as ${status}`);
      load();
      if (openBooking?.id === bk.id) setOpenBooking({ ...bk, status });
    } catch (e) { toast.error("Failed"); }
  };

  const currentBranch = branches.find((b) => b.id === (openBooking?.branch_id || branchId));

  return (
    <div data-testid="bookings-page">
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <div>
          <div className="eyebrow text-[#8A8D84]">Bookings calendar</div>
          <h1 className="font-display text-3xl lg:text-4xl font-semibold text-[#1A1C18]">
            {cursor.toLocaleString("en-US", { month: "long", year: "numeric" })}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Button data-testid="cal-prev" variant="outline" size="icon" className="h-10 w-10 rounded-xl"
            onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}><ChevronLeft className="h-4 w-4" /></Button>
          <Button data-testid="cal-today" variant="outline" className="h-10 rounded-xl"
            onClick={() => { const n = new Date(); setCursor(new Date(n.getFullYear(), n.getMonth(), 1)); }}>Today</Button>
          <Button data-testid="cal-next" variant="outline" size="icon" className="h-10 w-10 rounded-xl"
            onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}><ChevronRight className="h-4 w-4" /></Button>
          <Button data-testid="new-booking-btn"
            onClick={() => { setEditing(null); setFormOpen(true); }}
            className="h-10 rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white">
            <Plus className="h-4 w-4 mr-1.5" /> New booking
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-4 mb-3 text-xs text-[#5C6056]">
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-[#4A5D23]" /> In-House</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full bg-[#C84B31]" /> Outside Catering</span>
      </div>

      {/* Calendar Grid */}
      <div className="bg-white rounded-2xl border border-[#E5E0D8] shadow-soft overflow-hidden" data-testid="calendar-grid">
        <div className="grid grid-cols-7 bg-[#F9F8F6] border-b border-[#E5E0D8]">
          {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((d) => (
            <div key={d} className="eyebrow text-[#8A8D84] px-3 py-2.5 text-center">{d}</div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {cells.map((d, i) => {
            if (!d) return <div key={i} className="min-h-[110px] border-t border-r border-[#E5E0D8] bg-[#FAFAF8]" />;
            const ymd = fmtYMD(d);
            const list = bookingsByDate[ymd] || [];
            const isToday = ymd === fmtYMD(new Date());
            return (
              <button
                key={i}
                onClick={() => setDayPanel({ date: ymd, list })}
                data-testid={`cal-cell-${ymd}`}
                className={`text-left min-h-[110px] p-2 border-t border-r border-[#E5E0D8] hover:bg-[#F2EFE9] transition-colors ${
                  isToday ? "bg-[#F2EFE9]" : "bg-white"
                }`}
              >
                <div className={`text-sm font-semibold mb-1 ${isToday ? "text-[#4A5D23]" : "text-[#5C6056]"}`}>
                  {d.getDate()}
                </div>
                <div className="space-y-0.5">
                  {list.slice(0, 3).map((b) => (
                    <div key={b.id}
                      onClick={(e) => { e.stopPropagation(); setOpenBooking(b); }}
                      data-testid={`event-${b.id}`}
                      className={`event-pill ${b.status === "cancelled" ? "cancelled" : b.status === "completed" ? "completed" : b.venue_type}`}>
                      {b.event_time} {b.customer_name}
                    </div>
                  ))}
                  {list.length > 3 && <div className="text-[10px] text-[#8A8D84]">+{list.length - 3} more</div>}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Day panel */}
      <Dialog open={!!dayPanel} onOpenChange={(o) => !o && setDayPanel(null)}>
        <DialogContent className="max-w-lg rounded-2xl" data-testid="day-panel">
          <DialogHeader><DialogTitle className="font-display text-xl">
            Events on {dayPanel && new Date(dayPanel.date).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}
          </DialogTitle></DialogHeader>
          <div className="space-y-2 max-h-[60vh] overflow-auto">
            {dayPanel?.list.length === 0 && <p className="text-sm text-[#8A8D84]">No events scheduled.</p>}
            {dayPanel?.list.map((b) => (
              <button key={b.id} onClick={() => { setOpenBooking(b); setDayPanel(null); }}
                className="w-full text-left p-3 rounded-xl border border-[#E5E0D8] hover:bg-[#F2EFE9] flex items-center gap-3">
                <span className={`inline-block h-2.5 w-2.5 rounded-full ${b.venue_type === "in_house" ? "bg-[#4A5D23]" : "bg-[#C84B31]"}`} />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm">{b.event_time} · {b.customer_name}</div>
                  <div className="text-xs text-[#8A8D84] truncate">{b.venue_type === "in_house" ? "In-House" : "Outside"} · {b.num_people} guests</div>
                </div>
                <span className="text-xs font-medium text-[#5C6056]">{currency(computeTotals(b).total)}</span>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Booking detail */}
      <Dialog open={!!openBooking} onOpenChange={(o) => !o && setOpenBooking(null)}>
        <DialogContent className="max-w-2xl rounded-2xl" data-testid="booking-detail">
          {openBooking && <BookingDetail
            booking={openBooking}
            branch={currentBranch}
            settings={settings}
            onEdit={() => { setEditing(openBooking); setOpenBooking(null); setFormOpen(true); }}
            onCancel={() => markStatus(openBooking, "cancelled")}
            onComplete={() => markStatus(openBooking, "completed")}
          />}
        </DialogContent>
      </Dialog>

      {/* Booking form */}
      <Dialog open={formOpen} onOpenChange={(o) => { if (!o) { setFormOpen(false); setEditing(null); } }}>
        <DialogContent className="max-w-3xl rounded-2xl max-h-[90vh] overflow-auto" data-testid="booking-form-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-2xl">{editing ? "Edit booking" : "New booking"}</DialogTitle>
          </DialogHeader>
          <BookingForm
            branches={branches}
            currentBranchId={branchId !== "all" ? branchId : null}
            initial={editing}
            onCancel={() => { setFormOpen(false); setEditing(null); }}
            onSubmit={(payload) => submitBooking(payload, false)}
          />
        </DialogContent>
      </Dialog>

      {/* Conflict modal */}
      <Dialog open={!!conflict} onOpenChange={(o) => !o && setConflict(null)}>
        <DialogContent className="max-w-md rounded-2xl border-[#B33A3A]/30 bg-white/95 backdrop-blur-xl" data-testid="conflict-modal">
          <div className="text-center p-2">
            <div className="mx-auto h-14 w-14 rounded-2xl bg-[#FDF3F3] border border-[#EAB8B8] flex items-center justify-center mb-4">
              <AlertTriangle className="h-7 w-7 text-[#B33A3A]" />
            </div>
            <h3 className="font-display text-2xl font-semibold text-[#B33A3A] mb-2">Warning: Time Conflict Detected!</h3>
            <p className="text-sm text-[#5C6056] mb-6">
              Another booking already overlaps with this time window at this branch.
              Review both bookings before confirming.
            </p>
            <div className="flex gap-2 justify-center">
              <Button data-testid="conflict-close" variant="outline" className="h-11 rounded-xl px-5"
                onClick={() => setConflict(null)}>Close</Button>
              <Button data-testid="conflict-ignore" className="h-11 rounded-xl px-5 bg-[#B33A3A] hover:bg-[#9A3030] text-white"
                onClick={() => submitBooking(conflict.pendingPayload, true)}>Ignore and Continue</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function BookingDetail({ booking, branch, settings, onEdit, onCancel, onComplete }) {
  const t = computeTotals(booking);
  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-xs px-2 py-0.5 rounded-full text-white ${booking.venue_type === "in_house" ? "bg-[#4A5D23]" : "bg-[#C84B31]"}`}>
            {booking.venue_type === "in_house" ? "In-House" : "Outside Catering"}
          </span>
          {booking.status !== "booked" && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#F2EFE9] text-[#5C6056] capitalize">{booking.status}</span>
          )}
        </div>
        <h2 className="font-display text-2xl font-semibold">{booking.customer_name}</h2>
        <p className="text-sm text-[#5C6056]">{booking.phone}</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Info icon={Clock} label="Date & Time" value={`${booking.event_date} · ${booking.event_time}${booking.event_end_time ? `–${booking.event_end_time}` : ""}`} />
        <Info icon={Users} label="Guests" value={booking.num_people} />
        <Info icon={MapPin} label="Venue" value={booking.venue_address || (booking.venue_type === "in_house" ? "Party Hall" : "—")} />
        <Info icon={FileText} label="GST" value={`${booking.gst_percent}%`} />
      </div>

      <div className="rounded-xl border border-[#E5E0D8] divide-y divide-[#E5E0D8]">
        {booking.items.map((it) => (
          <div key={it.item_id} className="flex justify-between p-3 text-sm">
            <span>{it.name} <span className="text-[#8A8D84]">× {it.quantity}</span></span>
            <span className="font-medium">{currency(it.price * it.quantity)}</span>
          </div>
        ))}
      </div>

      <div className="space-y-1.5 text-sm">
        <Row label="Subtotal" value={currency(t.subtotal)} />
        {t.discount > 0 && <Row label="Discount" value={`− ${currency(t.discount)}`} />}
        <Row label={`GST (${t.gstPct}%)`} value={currency(t.gst)} />
        {t.transport > 0 && <Row label="Transportation" value={currency(t.transport)} />}
        <Row label="Total" value={currency(t.total)} bold />
        <Row label="Advance Paid" value={`− ${currency(t.advance)}`} />
        <Row label="Balance Due" value={currency(t.due)} accent />
      </div>

      {booking.notes && (
        <div className="rounded-xl bg-[#F2EFE9] p-3 text-sm text-[#5C6056]">
          <div className="eyebrow mb-1">Notes</div>
          {booking.notes}
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-2 border-t border-[#E5E0D8]">
        <Button data-testid="invoice-btn" className="rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white"
          onClick={() => generateInvoicePDF({ booking, branch, settings })}>
          <FileText className="h-4 w-4 mr-1.5" /> Generate Invoice
        </Button>
        {booking.status === "booked" && (
          <>
            <Button data-testid="edit-booking-btn" variant="outline" className="rounded-xl" onClick={onEdit}>
              <Pencil className="h-4 w-4 mr-1.5" /> Edit
            </Button>
            <Button data-testid="complete-booking-btn" variant="outline" className="rounded-xl border-[#4A5D23]/30 text-[#4A5D23] hover:bg-[#4A5D23]/5" onClick={onComplete}>
              <CheckCircle2 className="h-4 w-4 mr-1.5" /> Mark Completed
            </Button>
            <Button data-testid="cancel-booking-btn" variant="outline" className="rounded-xl border-[#B33A3A]/30 text-[#B33A3A] hover:bg-[#FDF3F3]" onClick={onCancel}>
              <XCircle className="h-4 w-4 mr-1.5" /> Cancel
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
function Info({ icon: Icon, label, value }) {
  return (
    <div className="rounded-xl bg-[#F9F8F6] border border-[#E5E0D8] p-3">
      <div className="flex items-center gap-1.5 mb-1 text-[#8A8D84]"><Icon className="h-3.5 w-3.5" /><span className="eyebrow">{label}</span></div>
      <div className="font-medium text-sm">{value}</div>
    </div>
  );
}
function Row({ label, value, bold, accent }) {
  return (
    <div className={`flex justify-between ${bold ? "font-semibold pt-1.5 border-t border-[#E5E0D8]" : ""} ${accent ? "text-[#C84B31] font-semibold text-base" : ""}`}>
      <span>{label}</span><span>{value}</span>
    </div>
  );
}
