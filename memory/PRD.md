# UD Catering — PRD

## Original problem statement
Production-ready Catering Management Web Application — 3 roles (User/Manager/Admin), branch-scoped operations, unified 3-tab login, calendar of bookings (In-House vs Outside), booking form with menu-by-category & financial breakdown, double-booking time-conflict modal, menu/staff/tax management for managers, admin analytics with daily/weekly/monthly/yearly sales and bookings, logo upload, PDF invoice generation.

## Architecture
- **Backend**: FastAPI + SQLAlchemy async + asyncpg + **Supabase Postgres** (transaction pooler). JWT (custom) auth with bcrypt. Alembic-managed schema. RLS enabled on every table.
- **Frontend**: React 19 + Tailwind + shadcn UI, react-router-dom, recharts, jsPDF, sonner, @supabase/supabase-js for **Realtime** subscriptions.
- **Theme**: Organic & Earthy — sage (#4A5D23), terracotta (#C84B31). Custom Outfit + IBM Plex Sans fonts.

## What's been implemented

### v1
Auth, branches, users (role RBAC), categories, menu items, bookings (exact-time conflict), analytics, settings (logo), seed.
Frontend: unified login (3 tabs), calendar with colored pills, day panel, booking detail/form, conflict modal, mgmt screens, analytics, PDF invoice.

### v2
- Migrated MongoDB → Supabase Postgres (SQLAlchemy + asyncpg + Alembic). RLS enabled on all 6 tables.
- Time-range overlap conflict (event_time + event_end_time).
- Weather widget removed; sidebar rebalanced.

### v3 (current)
- **Overnight events** — bookings store `start_at`/`end_at` TIMESTAMPTZ. If `event_end_time <= event_time`, end_at is next day. Conflict query uses absolute timestamps. Migration `3e900c505c71` backfills existing rows.
- **Supabase Realtime** — `bookings` added to `supabase_realtime` publication, anon SELECT policy added; frontend subscribes via `@supabase/supabase-js` and refreshes the calendar on any insert/update/delete. Staff in different browsers see the same calendar live.
- **Combined Discount input** — single number field + inline %/₹ dropdown (default %).
- **Eyebrow / overline fix** — renamed custom class from `overline` to `eyebrow` to avoid clash with Tailwind's built-in `overline` utility (which was drawing a line above the text).
- **Global font bump** — html base 16 → 17px; sidebar nav text-sm → text-base; calendar day numbers text-xs → text-sm; table content text-sm → text-base; event pills 11px → 12px. Better readability for staff.

## Test credentials
- Admin: `admin@udcatering.com` / `admin123`
- Manager 1: `manager1` / `manager123` (Main Hall)
- Manager 2: `manager2` / `manager123` (Downtown)
- Staff 1: `staff1` / `staff123` (Main Hall)
- Staff 2: `staff2` / `staff123` (Downtown)

## Known trade-offs / Backlog
- **Realtime privacy**: bookings_anon_read RLS policy exposes booking data (customer name/phone) to anyone with the public anon key (which ships in the browser bundle). Acceptable for an internal staff tool; restrict if app goes B2C.
- **Timezone**: start_at/end_at stamp the user's wall-clock time as UTC. For multi-timezone tenancy, persist a branch timezone and convert on save.
- HH:MM strings aren't strict-validated server-side (a malformed string would 500). Add a Pydantic regex.
- Analytics totals recomputed in Python; move to SQL aggregations at scale.
- P1: CSV export, SMS/email reminders (Twilio/Resend, would need keys).
- P2: Audit log, customer repeat-booking history, kitchen prep aggregation across 24-48h.
