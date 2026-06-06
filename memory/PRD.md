# UD Catering — PRD

## Original problem statement
Production-ready Catering Management Web Application with three roles (User/Manager/Admin), branch-scoped operations, unified 3-tab login, calendar view of bookings (In-House vs Outside), booking form with menu by category & financial breakdown, double-booking time-conflict modal, menu/staff/tax management for managers, admin analytics with daily/weekly/monthly/yearly sales and bookings, logo upload, and PDF invoice generation.

## Architecture (current)
- Backend: FastAPI + SQLAlchemy async + asyncpg + **Supabase Postgres** (transaction pooler). JWT auth with bcrypt; role-based dependencies.
- Schema: managed by Alembic (`/app/backend/alembic`). RLS **enabled** on every table (deny-all to anon/authenticated). Backend connects as `postgres` user via pooler — bypasses RLS — and enforces branch isolation at the application layer.
- Frontend: React + Tailwind + shadcn UI, react-router-dom, recharts, jsPDF, sonner.
- Theme: "Organic & Earthy" — sage (#4A5D23) primary, terracotta (#C84B31) secondary.

## What's been implemented

### v1 (2026-02-06)
- Auth, branches, users (role-aware RBAC), categories, menu items, bookings (exact-time conflict), analytics, settings (logo upload), seed.
- Frontend: unified login (3 tabs), calendar with colored event pills, day panel, booking detail, booking form with menu picker + live totals, conflict modal, menu/staff/branches mgmt, analytics dashboard, PDF invoice.

### v2 (2026-02-06)
- **Removed** weather widget + `/api/weather` endpoint; sidebar layout rebalanced with "Signed in as" footer.
- **Time-range overlap** conflict detection — bookings now require both `event_time` and `event_end_time`; conflict fires when intervals overlap; touching boundaries do NOT conflict; Pydantic validator enforces `end > start`.
- **Migrated to Supabase Postgres** via SQLAlchemy + asyncpg + Alembic (transaction pooler). RLS enabled on all six tables.
- Seed function now idempotent on Postgres.

## Test credentials
- Admin: `admin@udcatering.com` / `admin123`
- Manager 1: `manager1` / `manager123` (Main Hall); Manager 2: `manager2` / `manager123` (Downtown)
- Staff 1: `staff1` / `staff123` (Main Hall); Staff 2: `staff2` / `staff123` (Downtown)

## Backlog (P1/P2)
- P1: Overnight events (e.g. 22:00–02:00 next day) — store events as datetimes instead of HH:MM strings
- P1: DB CHECK constraints / Postgres enums for `role` and `status`
- P1: Print-friendly booking list / CSV export
- P1: SMS/Email reminders (Twilio/Resend)
- P2: Audit log for edits
- P2: Customer profiles with repeat-booking history
- P2: Optional real-time multi-user updates via Supabase realtime channels
