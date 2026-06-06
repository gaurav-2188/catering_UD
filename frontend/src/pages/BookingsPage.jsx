import React, { useEffect, useMemo, useState } from "react";
import api, { currency, computeTotals } from "../lib/api";
import { useAuth } from "../lib/auth";
import { supabase } from "../lib/supabase";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { ChevronLeft, ChevronRight, Plus, AlertTriangle } from "lucide-react";
import BookingForm from "./BookingForm";
import BookingDetail from "./BookingDetail";
import ConfirmDialog from "../components/ConfirmDialog";
import { toast } from "sonner";

function monthMatrix(year, month) {
  const first = new Date(year, month, 1);
  const startWeekday = first.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));
  while (cells.length % 7) cells.push(null);
  return cells;
}
const fmtYMD = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

// Module-level flag so we only skip the very first /bookings fetch on initial app boot,
// not every time the user navigates back to this page.
let _bootstrapConsumed = false;

export default function BookingsPage({ branches, branchId, settings, initialBookings = [] }) {
  const { user } = useAuth();
  const [bookings, setBookings] = useState(initialBookings);
  const [cursor, setCursor] = useState(() => { const n = new Date(); return new Date(n.getFullYear(), n.getMonth(), 1); });
  const [dayPanel, setDayPanel] = useState(null);
  const [openBooking, setOpenBooking] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [conflict, setConflict] = useState(null);
  const [confirm, setConfirm] = useState(null);
  // Skip the first refetch ONCE on the initial app boot — subsequent navigations always re-fetch.
  const skipFirstFetch = React.useRef(!_bootstrapConsumed && initialBookings && initialBookings.length >= 0);
  // While optimistic ops are in flight we don't want realtime to clobber the local placeholder.
  const pendingOps = React.useRef(0);

  const effectiveBranchId = user.role === "admin" ? branchId : user.branch_id;

  const load = async () => {
    if (pendingOps.current > 0) return; // server-of-truth refresh will happen after the in-flight op settles
    const params = user.role === "admin" && effectiveBranchId && effectiveBranchId !== "all" ? { branch_id: effectiveBranchId } : {};
    const r = await api.get("/bookings", { params });
    setBookings(r.data);
  };

  useEffect(() => {
    if (skipFirstFetch.current) {
      _bootstrapConsumed = true;
      skipFirstFetch.current = false;
      return;
    }
    load();
    /* eslint-disable-next-line */
  }, [effectiveBranchId]);

  // Live updates — narrowly scoped: filter on the currently-active branch when one is selected.
  // For Admin viewing "All branches", we intentionally subscribe without a filter.
  useEffect(() => {
    if (!supabase) return;
    const branchFilter = (effectiveBranchId && effectiveBranchId !== "all")
      ? `branch_id=eq.${effectiveBranchId}`
      : undefined;
    const ch = supabase
      .channel(`bookings_signal:${user.id}:${effectiveBranchId || "all"}`)
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "bookings_signal", ...(branchFilter ? { filter: branchFilter } : {}) }, () => load())
      .subscribe();
    return () => { supabase.removeChannel(ch); };
    /* eslint-disable-next-line */
  }, [user.id, effectiveBranchId]);

  // Calendar shows ONLY active "booked" events; completed & cancelled live in Previous Bookings.
  const calendarBookings = useMemo(() => bookings.filter((b) => b.status === "booked"), [bookings]);

  const bookingsByDate = useMemo(() => {
    const map = {};
    calendarBookings.forEach((b) => { (map[b.event_date] = map[b.event_date] || []).push(b); });
    Object.values(map).forEach((arr) => arr.sort((a, b) => a.event_time.localeCompare(b.event_time)));
    return map;
  }, [calendarBookings]);

  const cells = monthMatrix(cursor.getFullYear(), cursor.getMonth());

  const submitBooking = async (payload, ignore_conflict = false) => {
    const final = { ...payload, ignore_conflict };
    // EDIT path: keep the simpler await-then-replace flow so we don't lose the
    // user's pending edits if the patch fails.
    if (editing) {
      try {
        const r = await api.patch(`/bookings/${editing.id}`, final);
        setBookings((prev) => prev.map((b) => (b.id === editing.id ? r.data : b)));
        toast.success("Booking updated");
        setFormOpen(false); setEditing(null); setConflict(null);
      } catch (e) {
        const det = e.response?.data?.detail;
        if (e.response?.status === 409 && det?.code === "TIME_CONFLICT") {
          setConflict({ existing_id: det.existing_id, pendingPayload: payload });
        } else {
          toast.error(typeof det === "string" ? det : "Failed to save booking");
        }
      }
      return;
    }

    // CREATE path: instant modal close + temporary placeholder on the calendar,
    // then quiet background sync.
    const branchGst = branches.find((b) => b.id === payload.branch_id)?.gst_percent ?? 18;
    const tmpId = `tmp_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const optimistic = {
      id: tmpId, status: "booked", _optimistic: true,
      created_at: new Date().toISOString(), created_by: user.id,
      gst_percent: branchGst, total_amount: 0,
      ...payload,
    };
    setBookings((prev) => [...prev, optimistic]);
    setFormOpen(false); setEditing(null); setConflict(null);
    pendingOps.current += 1;
    try {
      const r = await api.post("/bookings", final);
      setBookings((prev) => prev.map((b) => (b.id === tmpId ? r.data : b)));
      toast.success("Booking created");
    } catch (e) {
      setBookings((prev) => prev.filter((b) => b.id !== tmpId));
      const det = e.response?.data?.detail;
      if (e.response?.status === 409 && det?.code === "TIME_CONFLICT") {
        // Reopen the form with the payload preserved, plus the conflict modal.
        setEditing(null);
        setFormOpen(false);
        setConflict({ existing_id: det.existing_id, pendingPayload: payload });
      } else {
        toast.error(typeof det === "string" ? det : "Failed to save booking — please try again.");
        // Reopen the form so the user doesn't lose their input.
        setEditing(null);
        setFormOpen(true);
      }
    } finally {
      pendingOps.current = Math.max(0, pendingOps.current - 1);
    }
  };

  const performStatusChange = async (bk, status) => {
    const snapshot = bookings;
    // Optimistic: instantly flip the local status so the calendar/archive update without waiting.
    setBookings((arr) => arr.map((b) => (b.id === bk.id ? { ...b, status } : b)));
    setConfirm(null);
    setOpenBooking(null);
    pendingOps.current += 1;
    try {
      const r = await api.patch(`/bookings/${bk.id}`, { status });
      setBookings((arr) => arr.map((b) => (b.id === bk.id ? r.data : b)));
      toast.success(status === "completed" ? "Booking marked as completed" : "Booking cancelled");
    } catch (e) {
      setBookings(snapshot);
      toast.error("Couldn't update the booking — reverting. Please try again.");
    } finally {
      pendingOps.current = Math.max(0, pendingOps.current - 1);
    }
  };

  const currentBranch = branches.find((b) => b.id === (openBooking?.branch_id || effectiveBranchId));

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

      <div className="flex items-center gap-4 mb-3 text-sm text-[#5C6056]">
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
                      onClick={(e) => { e.stopPropagation(); if (!b._optimistic) setOpenBooking(b); }}
                      data-testid={`event-${b.id}`}
                      title={b._optimistic ? "Saving…" : ""}
                      className={`event-pill ${b.venue_type} ${b._optimistic ? "opacity-60" : ""}`}>
                      {b.event_time} {b.customer_name}
                    </div>
                  ))}
                  {list.length > 3 && <div className="text-xs text-[#8A8D84]">+{list.length - 3} more</div>}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Day panel */}
      <Dialog open={!!dayPanel} onOpenChange={(o) => !o && setDayPanel(null)}>
        <DialogContent className="max-w-lg rounded-2xl max-h-[85vh] overflow-y-auto" data-testid="day-panel">
          <DialogHeader><DialogTitle className="font-display text-xl">
            Events on {dayPanel && new Date(dayPanel.date).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}
          </DialogTitle></DialogHeader>
          <div className="space-y-2">
            {dayPanel?.list.length === 0 && <p className="text-base text-[#8A8D84]">No events scheduled.</p>}
            {dayPanel?.list.map((b) => (
              <button key={b.id} onClick={() => { setOpenBooking(b); setDayPanel(null); }}
                className="w-full text-left p-3 rounded-xl border border-[#E5E0D8] hover:bg-[#F2EFE9] flex items-center gap-3">
                <span className={`inline-block h-2.5 w-2.5 rounded-full ${b.venue_type === "in_house" ? "bg-[#4A5D23]" : "bg-[#C84B31]"}`} />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-base">{b.event_time} · {b.customer_name}</div>
                  <div className="text-sm text-[#8A8D84] truncate">{b.venue_type === "in_house" ? "In-House" : "Outside"} · {b.num_people} guests</div>
                </div>
                <span className="text-sm font-medium text-[#5C6056]">{currency(computeTotals(b).total)}</span>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Booking detail */}
      <Dialog open={!!openBooking} onOpenChange={(o) => !o && setOpenBooking(null)}>
        <DialogContent className="max-w-2xl rounded-2xl max-h-[90vh] overflow-y-auto" data-testid="booking-detail">
          {openBooking && <BookingDetail
            booking={openBooking}
            branch={currentBranch}
            settings={settings}
            onEdit={() => { setEditing(openBooking); setOpenBooking(null); setFormOpen(true); }}
            onCancel={() => setConfirm({ kind: "cancel", booking: openBooking })}
            onComplete={() => setConfirm({ kind: "complete", booking: openBooking })}
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
            currentBranchId={effectiveBranchId !== "all" ? effectiveBranchId : null}
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
            <p className="text-base text-[#5C6056] mb-6">
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

      {/* Confirm Mark Completed / Cancel */}
      <ConfirmDialog
        open={!!confirm}
        onOpenChange={(o) => !o && setConfirm(null)}
        title={confirm?.kind === "complete" ? "Mark booking as completed?" : "Cancel this booking?"}
        description={confirm?.kind === "complete"
          ? "Once marked completed, this booking will be moved to Previous Bookings → Completed and removed from the calendar."
          : "Cancelled bookings move to Previous Bookings → Cancelled. They will no longer block the time slot for new bookings."}
        confirmLabel={confirm?.kind === "complete" ? "Yes, mark completed" : "Yes, cancel booking"}
        tone={confirm?.kind === "complete" ? "primary" : "danger"}
        onConfirm={() => confirm && performStatusChange(confirm.booking, confirm.kind === "complete" ? "completed" : "cancelled")}
      />
    </div>
  );
}
