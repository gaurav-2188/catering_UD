import React from "react";
import { currency, computeTotals } from "../lib/api";
import { Button } from "../components/ui/button";
import { generateInvoicePDF } from "../lib/pdf";
import { FileText, CheckCircle2, XCircle, Pencil, MapPin, Users, Clock } from "lucide-react";

export default function BookingDetail({ booking, branch, settings, onEdit, onCancel, onComplete }) {
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
        <p className="text-base text-[#5C6056]">{booking.phone}</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Info icon={Clock} label="Date & Time" value={`${booking.event_date} · ${booking.event_time}${booking.event_end_time ? `–${booking.event_end_time}` : ""}`} />
        <Info icon={Users} label="Guests" value={booking.num_people} />
        <Info icon={MapPin} label="Venue" value={booking.venue_address || (booking.venue_type === "in_house" ? "Party Hall" : "—")} />
        <Info icon={FileText} label="GST" value={`${booking.gst_percent}%`} />
      </div>

      <div>
        <div className="eyebrow text-[#8A8D84] mb-1.5">Menu · {currency(t.perPersonRate)}/person × {t.headcount}</div>
        <div className="rounded-xl border border-[#E5E0D8] divide-y divide-[#E5E0D8] max-h-56 overflow-y-auto" data-testid="detail-items-list">
          {booking.items.map((it) => (
            <div key={it.item_id} className="flex justify-between p-3 text-base">
              <span>{it.name}</span>
              <span className="font-medium text-[#5C6056]">{currency(it.price)} <span className="text-xs text-[#8A8D84]">/person</span></span>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-1.5 text-base">
        <Row label="Subtotal" value={currency(t.subtotal)} />
        {t.discount > 0 && <Row label="Discount" value={`− ${currency(t.discount)}`} />}
        <Row label={`GST (${t.gstPct}%)`} value={currency(t.gst)} />
        {t.transport > 0 && <Row label="Transportation" value={currency(t.transport)} />}
        <Row label="Total" value={currency(t.total)} bold />
        <Row label="Advance Paid" value={`− ${currency(t.advance)}`} />
        <Row label="Balance Due" value={currency(t.due)} accent />
      </div>

      {booking.notes && (
        <div className="rounded-xl bg-[#F2EFE9] p-3 text-base text-[#5C6056]">
          <div className="eyebrow mb-1">Notes</div>
          {booking.notes}
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-2 border-t border-[#E5E0D8]">
        <Button data-testid="invoice-btn" className="rounded-xl bg-[#4A5D23] hover:bg-[#3C4B1C] text-white"
          onClick={() => generateInvoicePDF({ booking, branch, settings })}>
          <FileText className="h-4 w-4 mr-1.5" /> Generate Invoice
        </Button>
        {booking.status === "booked" && onEdit && (
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
      <div className="font-medium text-base">{value}</div>
    </div>
  );
}
function Row({ label, value, bold, accent }) {
  return (
    <div className={`flex justify-between ${bold ? "font-semibold pt-1.5 border-t border-[#E5E0D8]" : ""} ${accent ? "text-[#C84B31] font-semibold text-lg" : ""}`}>
      <span>{label}</span><span>{value}</span>
    </div>
  );
}
