import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API });

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("ud_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

export default api;

export const currency = (n) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
    Number.isFinite(n) ? n : 0
  );

export function computeTotals(booking, gstPercentOverride) {
  const subtotal = (booking.items || []).reduce((s, it) => s + (it.price || 0) * (it.quantity || 0), 0);
  const discAmt = Number(booking.discount_amount || 0);
  const discPct = Number(booking.discount_percent || 0);
  const discount = discAmt + (subtotal * discPct) / 100;
  const taxable = Math.max(0, subtotal - discount);
  const gstPct = gstPercentOverride ?? booking.gst_percent ?? 18;
  const gst = (taxable * gstPct) / 100;
  const transport = Number(booking.transportation_cost || 0);
  const total = taxable + gst + transport;
  const advance = Number(booking.advance_paid || 0);
  const due = Math.max(0, total - advance);
  return { subtotal, discount, taxable, gst, transport, total, advance, due, gstPct };
}
