# UD Catering — PRD

## Original problem statement
Production-ready Catering Management Web Application with three roles (User/Manager/Admin), branch-scoped operations, unified 3-tab login, calendar view of bookings (In-House vs Outside), booking form with menu by category & financial breakdown, double-booking time-conflict modal, menu/staff/tax management for managers, admin analytics with daily/weekly/monthly/yearly sales and bookings, logo upload, and PDF invoice generation.

## User decisions (1st pass)
- Database: MongoDB (already configured; Supabase deferred)
- Weather: simulated forecast (5-day, with severity alerts)
- PDF: client-side jsPDF
- Currency: INR (₹); GST editable by Manager (own branch) and Admin (any branch)
- Seed: 1 admin + 2 branches + 2 managers + 2 staff + 6 menu categories per branch

## Architecture
- Backend: FastAPI + Motor + MongoDB (single `server.py`), JWT auth with bcrypt, role-based dependencies
- Frontend: React + Tailwind + shadcn UI, react-router-dom, recharts, jsPDF, sonner toasts
- Theme: "Organic & Earthy" — sage green primary (#4A5D23), terracotta secondary (#C84B31)

## What's been implemented (2026-02-06)
- Auth: `/api/auth/login` (with role), `/api/auth/me`
- Branches CRUD (admin); managers can update only GST
- Users CRUD with role-aware RBAC (managers create only branch staff)
- Categories + Menu Items CRUD (manager/admin per branch)
- Bookings CRUD with 409 TIME_CONFLICT detection and `ignore_conflict` bypass
- Analytics summary (today/week/month/year + 30-day & 12-month series)
- Settings: company logo upload (base64) by admin
- Weather: simulated 5-day forecast with severity alerts
- Frontend:
  - Unified login (3 tabs: Staff/Manager/Admin)
  - App layout: sticky header (logo + branch selector), sidebar nav + weather widget
  - Calendar view with colored event pills (sage = In-House, terracotta = Outside), chronological sorting
  - Day panel modal, Booking detail modal, Booking form with menu picker, financial preview
  - Center-screen TIME CONFLICT modal with Close / Ignore-and-Continue
  - Menu management (categories + items)
  - Staff/Users management (role-aware)
  - Branches CRUD (admin)
  - Branch settings (manager GST), Admin settings (logo + per-branch GST)
  - Analytics dashboard (stat cards + line + bar charts)
  - jsPDF invoice generation with logo, line items, totals, balance due

## Test credentials
- Admin: `admin@udcatering.com` / `admin123`
- Manager (Main Hall): `manager1` / `manager123`
- Manager (Downtown): `manager2` / `manager123`
- Staff (Main Hall): `staff1` / `staff123`
- Staff (Downtown): `staff2` / `staff123`

## Backlog (P0/P1/P2)
- P1: Print-friendly booking list / Export CSV
- P1: SMS/Email reminder to customers (Twilio integration)
- P1: Real weather API (OpenWeather) — would need API key from user
- P2: Time-range conflict (start–end) instead of exact-time match
- P2: Audit log of edits
- P2: Customer profiles with repeat-booking history
- P2: Switch from MongoDB to Supabase (if user wants relational analytics)
