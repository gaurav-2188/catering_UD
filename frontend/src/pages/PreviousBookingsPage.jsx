import React, { useEffect, useMemo, useState } from "react";
import api, { currency, computeTotals } from "../lib/api";
import { useAuth } from "../lib/auth";
import { supabase } from "../lib/supabase";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Button } from "../components/ui/button";
import { Dialog, DialogContent } from "../components/ui/dialog";
import BookingDetail from "./BookingDetail";
import ConfirmDialog from "../components/ConfirmDialog";
import { CheckCircle2, XCircle, FileText, History, Trash2 } from "lucide-react";
import { toast } from "sonner";

const formatDate = (s) => {
  try { return new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }); }
  catch { return s; }
};

export default function PreviousBookingsPage({ branches, branchId, settings, initialBookings = [] }) {
  const { user } = useAuth();
  const effective = user.role === "admin" ? branchId : user.branch_id;
  const [bookings, setBookings] = useState(initialBookings);
  const [tab, setTab] = useState("completed");
  const [open, setOpen] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null); // booking pending hard-delete confirm
  const pendingOps = React.useRef(0);

  const load = async () => {
    if (pendingOps.current > 0) return;
    const params = user.role === "admin" && effective && effective !== "all" ? { branch_id: effective } : {};
    const r = await api.get("/bookings", { params });
    setBookings(r.data);
  };

  const hardDelete = async (bk) => {
    const snapshot = bookings;
    // Optimistically remove the row
    setBookings((arr) => arr.filter((b) => b.id !== bk.id));
    setPendingDelete(null);
    pendingOps.current += 1;
    try {
      await api.delete(`/bookings/${bk.id}`);
      toast.success("Booking permanently deleted");
    } catch (e) {
      setBookings(snapshot);
      toast.error("Couldn't delete — reverted. Please try again.");
    } finally {
      pendingOps.current = Math.max(0, pendingOps.current - 1);
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [effective]);

  // Live updates — narrowly scoped to the active branch (or all branches for Admin)
  useEffect(() => {
    if (!supabase) return;
    const branchFilter = (effective && effective !== "all") ? `branch_id=eq.${effective}` : undefined;
    const ch = supabase
      .channel(`prev_signal:${user.id}:${effective || "all"}`)
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "bookings_signal", ...(branchFilter ? { filter: branchFilter } : {}) }, () => load())
      .subscribe();
    return () => { supabase.removeChannel(ch); };
    /* eslint-disable-next-line */
  }, [user.id, effective]);

  const sorted = useMemo(() => {
    return [...bookings].sort((a, b) => {
      const ka = `${a.event_date} ${a.event_time}`;
      const kb = `${b.event_date} ${b.event_time}`;
      return kb.localeCompare(ka); // newest first
    });
  }, [bookings]);

  const completed = sorted.filter((b) => b.status === "completed");
  const cancelled = sorted.filter((b) => b.status === "cancelled");

  const currentBranch = branches.find((b) => b.id === (open?.branch_id || effective));

  return (
    <div data-testid="previous-bookings-page">
      <div className="mb-6">
        <div className="eyebrow text-[#8A8D84]">Archive</div>
        <h1 className="font-display text-3xl lg:text-4xl font-semibold text-[#1A1C18]">Previous bookings</h1>
        <p className="text-base text-[#5C6056] mt-1.5">Completed and cancelled bookings, sorted with the most recent first.</p>
      </div>

      <Tabs value={tab} onValueChange={setTab} className="w-full">
        <TabsList className="bg-[#F2EFE9] p-1 rounded-xl h-auto inline-flex">
          <TabsTrigger
            value="completed"
            data-testid="tab-completed"
            className="data-[state=active]:bg-white data-[state=active]:text-[#4A5D23] data-[state=active]:shadow-sm rounded-lg px-4 py-2 text-base font-medium"
          >
            <CheckCircle2 className="h-4 w-4 mr-1.5" /> Completed
            <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-[#4A5D23]/10 text-[#4A5D23]">{completed.length}</span>
          </TabsTrigger>
          <TabsTrigger
            value="cancelled"
            data-testid="tab-cancelled"
            className="data-[state=active]:bg-white data-[state=active]:text-[#B33A3A] data-[state=active]:shadow-sm rounded-lg px-4 py-2 text-base font-medium"
          >
            <XCircle className="h-4 w-4 mr-1.5" /> Cancelled
            <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-[#B33A3A]/10 text-[#B33A3A]">{cancelled.length}</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="completed" className="mt-5">
          <ArchiveTable rows={completed} onView={setOpen} canDelete={user.role === "admin"} onDelete={setPendingDelete} emptyIcon={History} emptyMessage="No completed bookings yet." />
        </TabsContent>
        <TabsContent value="cancelled" className="mt-5">
          <ArchiveTable rows={cancelled} onView={setOpen} canDelete={user.role === "admin"} onDelete={setPendingDelete} emptyIcon={History} emptyMessage="No cancelled bookings yet." />
        </TabsContent>
      </Tabs>

      <Dialog open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        <DialogContent className="max-w-2xl rounded-2xl max-h-[90vh] overflow-y-auto" data-testid="archive-detail">
          {open && <BookingDetail booking={open} branch={currentBranch} settings={settings} />}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(o) => !o && setPendingDelete(null)}
        title="Delete this booking permanently?"
        description={pendingDelete
          ? `This will permanently remove ${pendingDelete.customer_name}'s booking from the database. This action cannot be undone.`
          : ""}
        confirmLabel="Yes, delete permanently"
        tone="danger"
        onConfirm={() => pendingDelete && hardDelete(pendingDelete)}
      />
    </div>
  );
}

function ArchiveTable({ rows, onView, canDelete, onDelete, emptyIcon: Icon, emptyMessage }) {
  if (!rows.length) {
    return (
      <div className="bg-white rounded-2xl border border-[#E5E0D8] shadow-soft p-12 text-center">
        <Icon className="h-10 w-10 text-[#8A8D84] mx-auto mb-3" />
        <p className="text-base text-[#5C6056]">{emptyMessage}</p>
      </div>
    );
  }
  return (
    <div className="bg-white rounded-2xl border border-[#E5E0D8] shadow-soft overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-base">
          <thead className="bg-[#F9F8F6] text-[#5C6056]">
            <tr>
              <th className="text-left p-3 eyebrow">Date</th>
              <th className="text-left p-3 eyebrow">Time</th>
              <th className="text-left p-3 eyebrow">Customer</th>
              <th className="text-left p-3 eyebrow">Phone</th>
              <th className="text-left p-3 eyebrow">Venue</th>
              <th className="text-right p-3 eyebrow">Total</th>
              <th className="text-right p-3 eyebrow">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => {
              const t = computeTotals(b);
              return (
                <tr key={b.id} className="border-t border-[#E5E0D8] hover:bg-[#F2EFE9]/60" data-testid={`archive-row-${b.id}`}>
                  <td className="p-3 font-medium whitespace-nowrap">{formatDate(b.event_date)}</td>
                  <td className="p-3 text-[#5C6056] whitespace-nowrap">{b.event_time}{b.event_end_time ? `–${b.event_end_time}` : ""}</td>
                  <td className="p-3 font-medium">{b.customer_name}</td>
                  <td className="p-3 text-[#5C6056] whitespace-nowrap">{b.phone}</td>
                  <td className="p-3">
                    <span className={`inline-block text-xs px-2 py-0.5 rounded-full text-white ${b.venue_type === "in_house" ? "bg-[#4A5D23]" : "bg-[#C84B31]"}`}>
                      {b.venue_type === "in_house" ? "In-House" : "Outside"}
                    </span>
                  </td>
                  <td className="p-3 text-right font-semibold whitespace-nowrap">{currency(t.total)}</td>
                  <td className="p-3 text-right whitespace-nowrap">
                    <div className="inline-flex items-center gap-1.5">
                      <Button
                        data-testid={`view-summary-${b.id}`}
                        variant="outline"
                        size="sm"
                        className="rounded-xl"
                        onClick={() => onView(b)}
                      >
                        <FileText className="h-3.5 w-3.5 mr-1" /> View Summary
                      </Button>
                      {canDelete && (
                        <Button
                          data-testid={`delete-perm-${b.id}`}
                          variant="ghost"
                          size="icon"
                          aria-label="Delete permanently"
                          title="Delete permanently"
                          className="h-9 w-9 rounded-xl text-[#B33A3A] hover:bg-[#FDF3F3]"
                          onClick={() => onDelete(b)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
