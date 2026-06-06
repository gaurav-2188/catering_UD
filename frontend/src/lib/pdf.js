import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { computeTotals } from "./api";

export function generateInvoicePDF({ booking, branch, settings, fileName }) {
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const t = computeTotals(booking);

  // Header
  if (settings?.company_logo && settings.company_logo.startsWith("data:image")) {
    try { doc.addImage(settings.company_logo, "PNG", 40, 30, 50, 50); } catch (e) { /* ignore broken logo */ }
  }
  doc.setFont("helvetica", "bold");
  doc.setFontSize(22);
  doc.setTextColor(74, 93, 35);
  doc.text("UD Catering", 100, 55);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(90);
  doc.text(branch?.name || "", 100, 72);
  if (branch?.address) doc.text(branch.address, 100, 86);

  doc.setFontSize(18);
  doc.setTextColor(20);
  doc.text("INVOICE", 555 - 40, 55, { align: "right" });
  doc.setFontSize(9);
  doc.setTextColor(120);
  doc.text(`Booking #${booking.id.slice(0, 8).toUpperCase()}`, 555 - 40, 72, { align: "right" });
  doc.text(`Issued: ${new Date().toLocaleDateString("en-IN")}`, 555 - 40, 86, { align: "right" });

  // Customer & event
  const y = 130;
  doc.setDrawColor(229, 224, 216);
  doc.line(40, y - 20, 555, y - 20);

  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.setTextColor(60);
  doc.text("BILL TO", 40, y);
  doc.text("EVENT DETAILS", 320, y);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  doc.setTextColor(20);
  doc.text(booking.customer_name, 40, y + 18);
  doc.setFontSize(9);
  doc.setTextColor(80);
  doc.text(`Phone: ${booking.phone}`, 40, y + 34);
  doc.text(`Guests: ${booking.num_people}`, 40, y + 48);

  doc.setFontSize(11);
  doc.setTextColor(20);
  doc.text(`${booking.event_date} • ${booking.event_time}${booking.event_end_time ? `–${booking.event_end_time}` : ""}`, 320, y + 18);
  doc.setFontSize(9);
  doc.setTextColor(80);
  doc.text(`Type: ${booking.venue_type === "in_house" ? "In-House" : "Outside Catering"}`, 320, y + 34);
  if (booking.venue_address) {
    const wrapped = doc.splitTextToSize(`Venue: ${booking.venue_address}`, 220);
    doc.text(wrapped, 320, y + 48);
  }

  // Items table: per-person pricing
  autoTable(doc, {
    startY: y + 90,
    head: [["#", "Item", "Per person (Rs)", `Guests`, "Amount (Rs)"]],
    body: booking.items.map((it, i) => [
      i + 1, it.name, Number(it.price).toFixed(2), booking.num_people, (Number(it.price) * booking.num_people).toFixed(2),
    ]),
    theme: "striped",
    headStyles: { fillColor: [74, 93, 35], textColor: 255, fontStyle: "bold" },
    styles: { font: "helvetica", fontSize: 10, cellPadding: 8 },
    margin: { left: 40, right: 40 },
  });

  let endY = doc.lastAutoTable.finalY + 20;

  const rows = [
    [`Subtotal (Rs ${t.perPersonRate.toFixed(0)}/guest × ${t.headcount})`, t.subtotal],
    ...(t.discount > 0 ? [["Discount", -t.discount]] : []),
    [`GST (${t.gstPct}%)`, t.gst],
    ...(t.transport > 0 ? [["Transportation", t.transport]] : []),
    ["Total", t.total],
    ["Advance Paid", -t.advance],
    ["Balance Due", t.due],
  ];

  doc.setFontSize(10);
  rows.forEach(([label, val], i) => {
    const isFinal = label === "Balance Due";
    doc.setFont("helvetica", isFinal ? "bold" : "normal");
    if (isFinal) { doc.setTextColor(200, 75, 49); } else { doc.setTextColor(60, 60, 60); }
    doc.text(String(label), 320, endY + i * 18);
    doc.text(`Rs ${Number(val).toFixed(2)}`, 555 - 40, endY + i * 18, { align: "right" });
  });

  endY += rows.length * 18 + 14;
  if (booking.notes) {
    doc.setFont("helvetica", "bold");
    doc.setTextColor(60);
    doc.setFontSize(10);
    doc.text("Notes", 40, endY);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(80);
    const w = doc.splitTextToSize(booking.notes, 300);
    doc.text(w, 40, endY + 14);
  }

  doc.setFontSize(8);
  doc.setTextColor(150);
  doc.text("Thank you for choosing UD Catering. This is a computer-generated invoice.", 40, 800);

  doc.save(fileName || `UD-Catering-${booking.customer_name}-${booking.event_date}.pdf`);
}
