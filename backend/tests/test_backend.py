"""
UD Catering — Iteration 2 backend regression suite.
DB: Supabase Postgres. Contract changes vs iter 1:
  - bookings require event_end_time
  - conflict detection is TIME-RANGE overlap (HTTP 409, detail.code='TIME_CONFLICT')
  - /api/weather endpoint removed (expect 404)
"""
import os
import uuid
from datetime import date, timedelta

import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://catering-management-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

# Future date well outside business calendar so test bookings won't collide with real data
TEST_DATE = (date.today() + timedelta(days=420)).isoformat()
TEST_TAG = f"TEST_{uuid.uuid4().hex[:6]}"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def s():
    return requests.Session()


def _login(s, username, password, role):
    r = s.post(f"{API}/auth/login", json={"username": username, "password": password, "role": role}, timeout=20)
    assert r.status_code == 200, f"login failed for {username}/{role}: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="session")
def admin(s):
    return _login(s, "admin@udcatering.com", "admin123", "admin")


@pytest.fixture(scope="session")
def manager1(s):
    return _login(s, "manager1", "manager123", "manager")


@pytest.fixture(scope="session")
def manager2(s):
    return _login(s, "manager2", "manager123", "manager")


@pytest.fixture(scope="session")
def staff1(s):
    return _login(s, "staff1", "staff123", "user")


@pytest.fixture(scope="session")
def staff2(s):
    return _login(s, "staff2", "staff123", "user")


def hdr(tok):
    return {"Authorization": f"Bearer {tok['token']}"}


@pytest.fixture(scope="session")
def branches(s, admin):
    r = s.get(f"{API}/branches", headers=hdr(admin), timeout=20)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="session")
def main_branch(branches, manager1):
    # the branch_id of manager1 is the source of truth for "Main Hall"
    bid = manager1["user"]["branch_id"]
    assert bid is not None
    return next(b for b in branches if b["id"] == bid)


@pytest.fixture(scope="session")
def downtown_branch(branches, manager2):
    bid = manager2["user"]["branch_id"]
    return next(b for b in branches if b["id"] == bid)


@pytest.fixture(scope="session")
def created_bookings():
    return []  # ids tracked for teardown


# ---------- Auth ----------
class TestAuth:
    def test_admin_login(self, admin):
        assert admin["user"]["role"] == "admin"
        assert admin["user"]["username"] == "admin@udcatering.com"
        assert isinstance(admin["token"], str) and len(admin["token"]) > 10

    def test_manager_login(self, manager1):
        assert manager1["user"]["role"] == "manager"
        assert manager1["user"]["branch_id"] is not None

    def test_staff_login(self, staff1):
        assert staff1["user"]["role"] == "user"
        assert staff1["user"]["branch_id"] is not None

    def test_me_admin(self, s, admin):
        r = s.get(f"{API}/auth/me", headers=hdr(admin))
        assert r.status_code == 200
        assert r.json()["id"] == admin["user"]["id"]

    def test_me_invalid_token(self, s):
        r = s.get(f"{API}/auth/me", headers={"Authorization": "Bearer bad.token.here"})
        assert r.status_code == 401

    def test_login_wrong_password(self, s):
        r = s.post(f"{API}/auth/login", json={"username": "admin@udcatering.com", "password": "wrong", "role": "admin"})
        assert r.status_code == 401


# ---------- Branches / Categories / Menu ----------
class TestSeed:
    def test_branches_seeded(self, branches):
        assert len(branches) >= 2
        for b in branches:
            assert b["gst_percent"] == 18 or float(b["gst_percent"]) == 18.0

    def test_categories_seeded(self, s, admin, main_branch, downtown_branch):
        for br in (main_branch, downtown_branch):
            r = s.get(f"{API}/categories", params={"branch_id": br["id"]}, headers=hdr(admin))
            assert r.status_code == 200
            cats = r.json()
            assert len(cats) >= 6, f"branch {br['name']} has only {len(cats)} categories"

    def test_menu_items_seeded(self, s, admin, main_branch, downtown_branch):
        for br in (main_branch, downtown_branch):
            r = s.get(f"{API}/menu-items", params={"branch_id": br["id"]}, headers=hdr(admin))
            assert r.status_code == 200
            items = r.json()
            assert len(items) >= 15, f"branch {br['name']} has only {len(items)} items"


# ---------- Weather removed ----------
class TestRemovedEndpoints:
    def test_weather_404(self, s, admin):
        r = s.get(f"{API}/weather", headers=hdr(admin))
        assert r.status_code == 404


# ---------- Bookings & conflict ----------
def _booking_payload(branch_id, start, end, name_suffix="A", date_=TEST_DATE):
    return {
        "branch_id": branch_id,
        "customer_name": f"{TEST_TAG}_{name_suffix}",
        "phone": "9999999999",
        "num_people": 20,
        "venue_type": "in_house",
        "venue_address": "",
        "event_date": date_,
        "event_time": start,
        "event_end_time": end,
        "items": [{"item_id": "x", "name": "Test", "price": 100, "quantity": 2}],
    }


class TestBookingsAndConflict:
    def test_staff_creates_booking_with_gst_stamp(self, s, staff1, main_branch, created_bookings):
        payload = _booking_payload(main_branch["id"], "18:00", "20:00", "base")
        r = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["event_end_time"] == "20:00"
        assert float(b["gst_percent"]) == 18.0
        assert b["status"] == "booked"
        created_bookings.append(b["id"])

    def test_overlap_partial_conflict(self, s, staff1, main_branch):
        # base 18-20, new 19-21 → overlap
        payload = _booking_payload(main_branch["id"], "19:00", "21:00", "overlap")
        r = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "TIME_CONFLICT"
        assert "existing_id" in r.json()["detail"]

    def test_touching_boundary_no_conflict(self, s, staff1, main_branch, created_bookings):
        # base 18-20, new 20-22 → touching, no overlap
        payload = _booking_payload(main_branch["id"], "20:00", "22:00", "touch")
        r = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        assert r.status_code == 200, r.text
        created_bookings.append(r.json()["id"])

    def test_fully_inside_conflict(self, s, staff1, main_branch):
        # base 18-20, new 18:30-19:30 → inside
        payload = _booking_payload(main_branch["id"], "18:30", "19:30", "inside")
        r = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "TIME_CONFLICT"

    def test_fully_containing_conflict(self, s, staff1, main_branch, created_bookings):
        # create a small one first 18:30-19:30 with ignore (since 18-20 covers it) ... use different date for clean container test
        local_date = (date.today() + timedelta(days=421)).isoformat()
        small = _booking_payload(main_branch["id"], "18:30", "19:30", "small", date_=local_date)
        r1 = s.post(f"{API}/bookings", json=small, headers=hdr(staff1))
        assert r1.status_code == 200, r1.text
        created_bookings.append(r1.json()["id"])
        # new 18-21 fully contains existing
        big = _booking_payload(main_branch["id"], "18:00", "21:00", "big", date_=local_date)
        r2 = s.post(f"{API}/bookings", json=big, headers=hdr(staff1))
        assert r2.status_code == 409
        assert r2.json()["detail"]["code"] == "TIME_CONFLICT"

    def test_ignore_conflict_bypass(self, s, staff1, main_branch, created_bookings):
        payload = _booking_payload(main_branch["id"], "19:00", "21:00", "bypass")
        payload["ignore_conflict"] = True
        r = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        assert r.status_code == 200, r.text
        created_bookings.append(r.json()["id"])

    def test_patch_time_triggers_conflict(self, s, staff1, main_branch, created_bookings):
        # Create on a unique date, then try to patch into an overlap with same-date base
        d = (date.today() + timedelta(days=422)).isoformat()
        base = _booking_payload(main_branch["id"], "10:00", "12:00", "patchbase", date_=d)
        rb = s.post(f"{API}/bookings", json=base, headers=hdr(staff1))
        assert rb.status_code == 200
        base_id = rb.json()["id"]
        created_bookings.append(base_id)
        other = _booking_payload(main_branch["id"], "14:00", "16:00", "patchother", date_=d)
        ro = s.post(f"{API}/bookings", json=other, headers=hdr(staff1))
        assert ro.status_code == 200
        other_id = ro.json()["id"]
        created_bookings.append(other_id)
        # Try to move "other" into overlap with base
        r = s.patch(f"{API}/bookings/{other_id}", json={"event_time": "11:00", "event_end_time": "13:00"}, headers=hdr(staff1))
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "TIME_CONFLICT"

    def test_patch_status_completed(self, s, staff1, main_branch, created_bookings):
        d = (date.today() + timedelta(days=423)).isoformat()
        p = _booking_payload(main_branch["id"], "09:00", "10:00", "compl", date_=d)
        rb = s.post(f"{API}/bookings", json=p, headers=hdr(staff1))
        bid = rb.json()["id"]
        created_bookings.append(bid)
        r = s.patch(f"{API}/bookings/{bid}", json={"status": "completed"}, headers=hdr(staff1))
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_cancelled_booking_does_not_conflict(self, s, staff1, main_branch, created_bookings):
        d = (date.today() + timedelta(days=424)).isoformat()
        p = _booking_payload(main_branch["id"], "18:00", "20:00", "cancelme", date_=d)
        rb = s.post(f"{API}/bookings", json=p, headers=hdr(staff1))
        bid = rb.json()["id"]
        created_bookings.append(bid)
        # cancel it
        r = s.patch(f"{API}/bookings/{bid}", json={"status": "cancelled"}, headers=hdr(staff1))
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"
        # New overlapping booking should succeed
        p2 = _booking_payload(main_branch["id"], "19:00", "21:00", "afterCancel", date_=d)
        r2 = s.post(f"{API}/bookings", json=p2, headers=hdr(staff1))
        assert r2.status_code == 200, r2.text
        created_bookings.append(r2.json()["id"])

    def test_staff_cross_branch_forbidden(self, s, staff1, downtown_branch):
        p = _booking_payload(downtown_branch["id"], "08:00", "09:00", "cross")
        r = s.post(f"{API}/bookings", json=p, headers=hdr(staff1))
        assert r.status_code == 403


# ---------- Iteration 3: overnight bookings + start_at/end_at ----------
class TestOvernightBookings:
    """Iteration 3: end_time <= start_time means OVERNIGHT (end is next day).
    Conflict detection uses absolute start_at/end_at timestamps."""

    def test_overnight_booking_accepted_and_end_at_next_day(self, s, staff1, main_branch, created_bookings):
        d = (date.today() + timedelta(days=430)).isoformat()
        payload = _booking_payload(main_branch["id"], "22:00", "02:00", "overnight", date_=d)
        r = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        assert r.status_code == 200, r.text
        b = r.json()
        created_bookings.append(b["id"])
        # Response must include start_at and end_at as ISO strings
        assert "start_at" in b and isinstance(b["start_at"], str)
        assert "end_at" in b and isinstance(b["end_at"], str)
        assert b["start_at"].startswith(d + "T22:00")
        # end_at must be on the NEXT day at 02:00
        next_day = (date.today() + timedelta(days=431)).isoformat()
        assert b["end_at"].startswith(next_day + "T02:00"), f"expected end_at on {next_day}, got {b['end_at']}"
        assert b["event_time"] == "22:00"
        assert b["event_end_time"] == "02:00"

    def test_response_includes_start_at_end_at_for_normal_booking(self, s, staff1, main_branch, created_bookings):
        d = (date.today() + timedelta(days=431)).isoformat()
        payload = _booking_payload(main_branch["id"], "10:00", "12:00", "normal_iso", date_=d)
        r = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        assert r.status_code == 200, r.text
        b = r.json()
        created_bookings.append(b["id"])
        assert b["start_at"].startswith(d + "T10:00")
        assert b["end_at"].startswith(d + "T12:00")  # same day

    def test_same_date_overlap_with_overnight(self, s, staff1, main_branch, created_bookings):
        # existing 22:00-02:00 (overnight); new 21:00-23:00 same date -> overlap on day X
        d = (date.today() + timedelta(days=432)).isoformat()
        base = _booking_payload(main_branch["id"], "22:00", "02:00", "ovn_base", date_=d)
        rb = s.post(f"{API}/bookings", json=base, headers=hdr(staff1))
        assert rb.status_code == 200, rb.text
        created_bookings.append(rb.json()["id"])
        new = _booking_payload(main_branch["id"], "21:00", "23:00", "ovn_overlap", date_=d)
        r = s.post(f"{API}/bookings", json=new, headers=hdr(staff1))
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "TIME_CONFLICT"
        assert "existing_id" in r.json()["detail"]

    def test_cross_date_overlap_with_overnight(self, s, staff1, main_branch, created_bookings):
        # existing 22:00-02:00 on day X (overnight); new 01:00-03:00 on day X+1 -> overlap
        d1 = (date.today() + timedelta(days=433)).isoformat()
        d2 = (date.today() + timedelta(days=434)).isoformat()
        base = _booking_payload(main_branch["id"], "22:00", "02:00", "xdate_base", date_=d1)
        rb = s.post(f"{API}/bookings", json=base, headers=hdr(staff1))
        assert rb.status_code == 200, rb.text
        created_bookings.append(rb.json()["id"])
        new = _booking_payload(main_branch["id"], "01:00", "03:00", "xdate_overlap", date_=d2)
        r = s.post(f"{API}/bookings", json=new, headers=hdr(staff1))
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "TIME_CONFLICT"

    def test_cross_date_non_overlap_after_overnight(self, s, staff1, main_branch, created_bookings):
        # existing 22:00-02:00 on day X (overnight); new 03:00-05:00 on day X+1 -> no overlap
        d1 = (date.today() + timedelta(days=435)).isoformat()
        d2 = (date.today() + timedelta(days=436)).isoformat()
        base = _booking_payload(main_branch["id"], "22:00", "02:00", "noxov_base", date_=d1)
        rb = s.post(f"{API}/bookings", json=base, headers=hdr(staff1))
        assert rb.status_code == 200, rb.text
        created_bookings.append(rb.json()["id"])
        new = _booking_payload(main_branch["id"], "03:00", "05:00", "noxov_ok", date_=d2)
        r = s.post(f"{API}/bookings", json=new, headers=hdr(staff1))
        assert r.status_code == 200, r.text
        created_bookings.append(r.json()["id"])

    def test_patch_recomputes_start_at_end_at(self, s, staff1, main_branch, created_bookings):
        # Create normal booking, PATCH to overnight, verify end_at moves to next day
        d = (date.today() + timedelta(days=437)).isoformat()
        p = _booking_payload(main_branch["id"], "09:00", "10:00", "patch_recompute", date_=d)
        rb = s.post(f"{API}/bookings", json=p, headers=hdr(staff1))
        assert rb.status_code == 200
        bid = rb.json()["id"]
        created_bookings.append(bid)
        r = s.patch(f"{API}/bookings/{bid}",
                    json={"event_time": "23:00", "event_end_time": "01:00"}, headers=hdr(staff1))
        assert r.status_code == 200, r.text
        b = r.json()
        next_day = (date.today() + timedelta(days=438)).isoformat()
        assert b["start_at"].startswith(d + "T23:00")
        assert b["end_at"].startswith(next_day + "T01:00"), f"expected end_at on {next_day}, got {b['end_at']}"

    def test_patch_conflict_check_uses_new_range(self, s, staff1, main_branch, created_bookings):
        # Create two non-conflicting bookings, then PATCH one into the other's range -> 409
        d = (date.today() + timedelta(days=439)).isoformat()
        a = _booking_payload(main_branch["id"], "10:00", "11:00", "pc_a", date_=d)
        ra = s.post(f"{API}/bookings", json=a, headers=hdr(staff1))
        assert ra.status_code == 200, ra.text
        created_bookings.append(ra.json()["id"])
        b_payload = _booking_payload(main_branch["id"], "15:00", "16:00", "pc_b", date_=d)
        rb = s.post(f"{API}/bookings", json=b_payload, headers=hdr(staff1))
        assert rb.status_code == 200
        bid = rb.json()["id"]
        created_bookings.append(bid)
        # PATCH b to overlap a (10:30-10:45)
        r = s.patch(f"{API}/bookings/{bid}",
                    json={"event_time": "10:30", "event_end_time": "10:45"}, headers=hdr(staff1))
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "TIME_CONFLICT"

    def test_discount_percent_only_accepted(self, s, staff1, main_branch, created_bookings):
        # Iteration 3 frontend writes one of discount_amount/discount_percent. Contract unchanged.
        d = (date.today() + timedelta(days=440)).isoformat()
        payload = _booking_payload(main_branch["id"], "12:00", "13:00", "discpct", date_=d)
        payload["discount_percent"] = 10
        payload["discount_amount"] = 0
        r = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        assert r.status_code == 200, r.text
        b = r.json()
        created_bookings.append(b["id"])
        assert float(b["discount_percent"]) == 10.0
        assert float(b["discount_amount"]) == 0.0


# ---------- Users RBAC ----------
class TestUsersRBAC:
    def test_manager_creates_user(self, s, manager1, created_user_ids):
        uname = f"{TEST_TAG}_u_{uuid.uuid4().hex[:4]}"
        r = s.post(f"{API}/users", json={"username": uname, "password": "pw12345", "role": "user"}, headers=hdr(manager1))
        assert r.status_code == 200, r.text
        u = r.json()
        assert u["role"] == "user"
        assert u["branch_id"] == manager1["user"]["branch_id"]
        created_user_ids.append(u["id"])

    def test_manager_cannot_create_manager(self, s, manager1):
        r = s.post(f"{API}/users", json={"username": f"{TEST_TAG}_mgr", "password": "pw12345", "role": "manager"}, headers=hdr(manager1))
        assert r.status_code == 403

    def test_manager_cannot_create_admin(self, s, manager1):
        r = s.post(f"{API}/users", json={"username": f"{TEST_TAG}_ad", "password": "pw12345", "role": "admin"}, headers=hdr(manager1))
        assert r.status_code == 403


@pytest.fixture(scope="session")
def created_user_ids():
    return []


# ---------- Branch admin/manager updates ----------
class TestBranchAdmin:
    def test_admin_create_branch(self, s, admin, created_branch_ids):
        r = s.post(f"{API}/branches", json={"name": f"{TEST_TAG}_br", "address": "addr", "gst_percent": 12.0}, headers=hdr(admin))
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["name"] == f"{TEST_TAG}_br"
        assert float(b["gst_percent"]) == 12.0
        created_branch_ids.append(b["id"])

    def test_admin_update_branch_fields(self, s, admin, created_branch_ids):
        bid = created_branch_ids[0]
        r = s.patch(f"{API}/branches/{bid}", json={"name": f"{TEST_TAG}_br2", "address": "addr2", "gst_percent": 5.0}, headers=hdr(admin))
        assert r.status_code == 200
        b = r.json()
        assert b["name"] == f"{TEST_TAG}_br2"
        assert b["address"] == "addr2"
        assert float(b["gst_percent"]) == 5.0

    def test_manager_can_only_update_gst(self, s, manager1, main_branch):
        original_name = main_branch["name"]
        r = s.patch(f"{API}/branches/{main_branch['id']}",
                    json={"name": "HACKED", "gst_percent": 17.0}, headers=hdr(manager1))
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["name"] == original_name  # name change silently ignored
        assert float(b["gst_percent"]) == 17.0
        # restore
        s.patch(f"{API}/branches/{main_branch['id']}", json={"gst_percent": 18.0}, headers=hdr(manager1))

    def test_manager_cannot_update_other_branch(self, s, manager1, downtown_branch):
        r = s.patch(f"{API}/branches/{downtown_branch['id']}", json={"gst_percent": 9.0}, headers=hdr(manager1))
        assert r.status_code == 403


@pytest.fixture(scope="session")
def created_branch_ids():
    return []


# ---------- Analytics & Settings ----------
class TestAnalyticsAndSettings:
    def test_analytics_summary_shape(self, s, admin):
        r = s.get(f"{API}/analytics/summary", headers=hdr(admin))
        assert r.status_code == 200
        d = r.json()
        for k in ("daily", "weekly", "monthly", "yearly", "daily_series", "monthly_series"):
            assert k in d
        for k in ("daily", "weekly", "monthly", "yearly"):
            assert "bookings" in d[k] and "sales" in d[k]
        assert isinstance(d["daily_series"], list)
        assert isinstance(d["monthly_series"], list)

    def test_admin_updates_settings_logo(self, s, admin):
        logo = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        r = s.patch(f"{API}/settings", json={"id": "global", "company_logo": logo}, headers=hdr(admin))
        assert r.status_code == 200
        assert r.json()["company_logo"] == logo
        r2 = s.get(f"{API}/settings")
        assert r2.status_code == 200
        assert r2.json()["company_logo"] == logo


# ---------- Iteration 4: regex validators, per-person pricing, total_amount cache, realtime/policies ----------
def _expected_total(per_person_items_sum, num_people, gst_percent, discount_amount=0, discount_percent=0, transportation_cost=0):
    subtotal = per_person_items_sum * num_people
    discount = discount_amount + subtotal * discount_percent / 100
    taxable = max(0.0, subtotal - discount)
    gst = taxable * gst_percent / 100
    return taxable + gst + transportation_cost


class TestIter4Validators:
    """Iteration 4: BookingCreate/Update now have HH:MM and YYYY-MM-DD regex validators -> 422 (not 500)."""

    def test_create_invalid_event_time_returns_422(self, s, staff1, main_branch):
        p = _booking_payload(main_branch["id"], "25:00", "20:00", "badtime")
        r = s.post(f"{API}/bookings", json=p, headers=hdr(staff1))
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
        body = r.text.lower()
        assert "event_time" in body or "hh:mm" in body or "pattern" in body or "string_pattern_mismatch" in body

    def test_create_invalid_event_date_returns_422(self, s, staff1, main_branch):
        p = _booking_payload(main_branch["id"], "10:00", "11:00", "baddate", date_="08-2027-01")
        r = s.post(f"{API}/bookings", json=p, headers=hdr(staff1))
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
        body = r.text.lower()
        assert "event_date" in body or "yyyy" in body or "pattern" in body or "string_pattern_mismatch" in body

    def test_patch_invalid_event_time_returns_422(self, s, staff1, main_branch, created_bookings):
        d = (date.today() + timedelta(days=445)).isoformat()
        p = _booking_payload(main_branch["id"], "08:00", "09:00", "patch_v_base", date_=d)
        rb = s.post(f"{API}/bookings", json=p, headers=hdr(staff1))
        assert rb.status_code == 200, rb.text
        bid = rb.json()["id"]
        created_bookings.append(bid)
        r = s.patch(f"{API}/bookings/{bid}", json={"event_time": "9:5"}, headers=hdr(staff1))
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"

    def test_patch_invalid_event_date_returns_422(self, s, staff1, main_branch, created_bookings):
        d = (date.today() + timedelta(days=446)).isoformat()
        p = _booking_payload(main_branch["id"], "08:00", "09:00", "patch_v_d", date_=d)
        rb = s.post(f"{API}/bookings", json=p, headers=hdr(staff1))
        assert rb.status_code == 200, rb.text
        created_bookings.append(rb.json()["id"])
        r = s.patch(f"{API}/bookings/{rb.json()['id']}", json={"event_date": "08-2027-01"}, headers=hdr(staff1))
        assert r.status_code == 422, r.text


class TestIter4PerPersonPricing:
    """Iteration 4: total_amount is cached on booking row; subtotal = sum(item.price) * num_people."""

    def test_total_amount_per_person_with_gst(self, s, staff1, main_branch, created_bookings):
        d = (date.today() + timedelta(days=450)).isoformat()
        payload = _booking_payload(main_branch["id"], "10:00", "11:00", "pp1", date_=d)
        payload["num_people"] = 50
        payload["items"] = [
            {"item_id": "x1", "name": "Veg", "price": 280, "quantity": 1},
            {"item_id": "x2", "name": "NonVeg", "price": 380, "quantity": 1},
        ]
        payload["discount_amount"] = 0
        payload["discount_percent"] = 0
        payload["transportation_cost"] = 0
        r = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        assert r.status_code == 200, r.text
        b = r.json()
        created_bookings.append(b["id"])
        gst = float(b["gst_percent"])  # seeded 18
        expected = _expected_total(280 + 380, 50, gst)  # (280+380)*50*1.18 = 38,940
        assert abs(b["total_amount"] - expected) < 0.01, f"expected {expected}, got {b['total_amount']}"
        # quantity should be effectively ignored — same total if quantity were doubled
        # (verified indirectly: expected uses per_person_rate=price only)

    def test_total_amount_quantity_is_ignored(self, s, staff1, main_branch, created_bookings):
        """Send quantity=10 -> total_amount should still be sum(price) * num_people * (1+gst)."""
        d = (date.today() + timedelta(days=451)).isoformat()
        payload = _booking_payload(main_branch["id"], "10:00", "11:00", "ppQ", date_=d)
        payload["num_people"] = 20
        payload["items"] = [{"item_id": "x", "name": "Test", "price": 100, "quantity": 10}]
        r = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        assert r.status_code == 200, r.text
        b = r.json()
        created_bookings.append(b["id"])
        gst = float(b["gst_percent"])
        expected = _expected_total(100, 20, gst)  # 100*20*1.18 = 2360
        assert abs(b["total_amount"] - expected) < 0.01, f"qty ignored expected {expected}, got {b['total_amount']}"

    def test_patch_num_people_recomputes_total(self, s, staff1, main_branch, created_bookings):
        d = (date.today() + timedelta(days=452)).isoformat()
        payload = _booking_payload(main_branch["id"], "10:00", "11:00", "ppPATCH", date_=d)
        payload["num_people"] = 10
        payload["items"] = [{"item_id": "x", "name": "Test", "price": 200, "quantity": 1}]
        r = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        assert r.status_code == 200, r.text
        b = r.json()
        bid = b["id"]
        created_bookings.append(bid)
        gst = float(b["gst_percent"])
        assert abs(b["total_amount"] - _expected_total(200, 10, gst)) < 0.01
        # PATCH num_people 10 -> 25
        r2 = s.patch(f"{API}/bookings/{bid}", json={"num_people": 25}, headers=hdr(staff1))
        assert r2.status_code == 200, r2.text
        b2 = r2.json()
        assert abs(b2["total_amount"] - _expected_total(200, 25, gst)) < 0.01, f"got {b2['total_amount']}"

    def test_patch_items_and_discount_recomputes_total(self, s, staff1, main_branch, created_bookings):
        d = (date.today() + timedelta(days=453)).isoformat()
        payload = _booking_payload(main_branch["id"], "10:00", "11:00", "ppItems", date_=d)
        payload["num_people"] = 30
        payload["items"] = [{"item_id": "x", "name": "Test", "price": 150, "quantity": 1}]
        r = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        bid = r.json()["id"]
        created_bookings.append(bid)
        gst = float(r.json()["gst_percent"])
        # New items 100+250 per_person, discount_amount=500
        new_items = [
            {"item_id": "n1", "name": "A", "price": 100, "quantity": 1},
            {"item_id": "n2", "name": "B", "price": 250, "quantity": 1},
        ]
        r2 = s.patch(f"{API}/bookings/{bid}",
                     json={"items": new_items, "discount_amount": 500}, headers=hdr(staff1))
        assert r2.status_code == 200, r2.text
        expected = _expected_total(350, 30, gst, discount_amount=500)
        assert abs(r2.json()["total_amount"] - expected) < 0.01, f"got {r2.json()['total_amount']}"


class TestIter4AnalyticsConsistency:
    """Iteration 4: /analytics/summary uses SUM(total_amount) via pure SQL. Shape unchanged."""

    def test_analytics_summary_uses_stored_totals(self, s, admin):
        r = s.get(f"{API}/analytics/summary", headers=hdr(admin))
        assert r.status_code == 200
        data = r.json()
        # Same shape contract
        for k in ("daily", "weekly", "monthly", "yearly", "daily_series", "monthly_series"):
            assert k in data
        # Sales fields are numeric and non-negative
        for bucket in ("daily", "weekly", "monthly", "yearly"):
            assert isinstance(data[bucket]["bookings"], int)
            assert isinstance(data[bucket]["sales"], (int, float))
            assert data[bucket]["sales"] >= 0
            assert data[bucket]["bookings"] >= 0
        # Yearly sales >= monthly >= weekly >= daily (monotone since totals are non-negative)
        ds = data["daily"]["sales"]; ws = data["weekly"]["sales"]
        ms = data["monthly"]["sales"]; ys = data["yearly"]["sales"]
        assert ws >= ds, f"weekly {ws} should be >= daily {ds}"
        assert ms >= ws, f"monthly {ms} should be >= weekly {ws}"
        assert ys >= ms, f"yearly {ys} should be >= monthly {ms}"

    def test_analytics_sales_matches_sum_of_listed_total_amount(self, s, admin):
        """The 'yearly' sales bucket should equal SUM(total_amount) of all bookings whose
        event_date falls in the current year. We compute that from GET /api/bookings."""
        from datetime import datetime as _dt
        year = _dt.utcnow().year
        rb = s.get(f"{API}/bookings", headers=hdr(admin))
        assert rb.status_code == 200
        bookings = rb.json()
        # NOTE: server.py 'yearly' bucket actually uses predicate `event_date >= year_start`
        # so it catches ALL bookings from Jan 1 of current year onwards INCLUDING future-dated ones.
        # (Naming is misleading — see code review note.)
        year_start = f"{year}-01-01"
        expected_year_sum = sum(
            float(b.get("total_amount") or 0)
            for b in bookings
            if (b.get("event_date") or "") >= year_start
            and b.get("status") != "cancelled"
        )
        r = s.get(f"{API}/analytics/summary", headers=hdr(admin))
        assert r.status_code == 200
        ys = float(r.json()["yearly"]["sales"])
        # Allow small float tolerance (DB float vs Python float rounding)
        assert abs(ys - expected_year_sum) < 1.0, f"yearly sales {ys} vs expected {expected_year_sum}"


class TestIter4ListBookingsCompleted:
    """Completed bookings still appear in GET /api/bookings (frontend filters client-side)."""

    def test_completed_booking_listed_by_get_bookings(self, s, staff1, main_branch, created_bookings):
        d = (date.today() + timedelta(days=455)).isoformat()
        p = _booking_payload(main_branch["id"], "09:00", "10:00", "complListed", date_=d)
        rb = s.post(f"{API}/bookings", json=p, headers=hdr(staff1))
        assert rb.status_code == 200, rb.text
        bid = rb.json()["id"]
        created_bookings.append(bid)
        r1 = s.patch(f"{API}/bookings/{bid}", json={"status": "completed"}, headers=hdr(staff1))
        assert r1.status_code == 200
        assert r1.json()["status"] == "completed"
        r2 = s.get(f"{API}/bookings", headers=hdr(staff1))
        assert r2.status_code == 200
        ids_and_status = [(b["id"], b["status"]) for b in r2.json()]
        assert (bid, "completed") in ids_and_status, "completed booking must still be returned by GET /api/bookings"


# ---------- Iteration 4: DB-level realtime publication / policies / trigger ----------
def _db_dsn():
    """Read DATABASE_URL from /app/backend/.env (we don't want to clobber env)."""
    path = "/app/backend/.env"
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("DATABASE_URL"):
                    _, _, val = line.partition("=")
                    return val.strip().strip('"').strip("'")
    except Exception:
        return None
    return None


@pytest.fixture(scope="session")
def pg_conn():
    import psycopg2
    dsn = _db_dsn()
    if not dsn:
        pytest.skip("DATABASE_URL not found in /app/backend/.env")
    try:
        conn = psycopg2.connect(dsn, connect_timeout=15)
        conn.autocommit = True
    except Exception as e:
        pytest.skip(f"cannot reach Postgres: {e}")
        return
    yield conn
    conn.close()


class TestIter4Realtime:
    def test_publication_includes_bookings_signal_not_bookings(self, pg_conn):
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT tablename FROM pg_publication_tables "
            "WHERE pubname = 'supabase_realtime' AND schemaname = 'public'"
        )
        tables = {row[0] for row in cur.fetchall()}
        cur.close()
        assert "bookings_signal" in tables, f"bookings_signal missing from publication; have {tables}"
        assert "bookings" not in tables, f"bookings table must NOT be in realtime publication; have {tables}"

    def test_anon_policy_only_on_bookings_signal(self, pg_conn):
        cur = pg_conn.cursor()
        cur.execute(
            """
            SELECT tablename, policyname, roles
            FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename LIKE 'booking%'
            """
        )
        rows = cur.fetchall()
        cur.close()
        # Filter to policies that include 'anon' in roles
        anon_policies = []
        for tablename, policyname, roles in rows:
            roles_list = list(roles) if roles is not None else []
            if any("anon" in str(r) for r in roles_list):
                anon_policies.append((tablename, policyname))
        # Should have at least one and only the bookings_signal_anon_read on bookings_signal
        assert anon_policies, f"no anon policies found among booking* tables; rows={rows}"
        for tablename, policyname in anon_policies:
            assert tablename == "bookings_signal", (
                f"anon policy on '{tablename}' (policy '{policyname}') — should only be on bookings_signal. all: {anon_policies}"
            )
        names = {p for _, p in anon_policies}
        assert "bookings_signal_anon_read" in names, f"bookings_signal_anon_read policy missing; have {names}"

    def test_trigger_emits_signal_on_booking_insert(self, s, staff1, main_branch, created_bookings, pg_conn):
        d = (date.today() + timedelta(days=460)).isoformat()
        p = _booking_payload(main_branch["id"], "08:00", "09:00", "sig_insert", date_=d)
        rb = s.post(f"{API}/bookings", json=p, headers=hdr(staff1))
        assert rb.status_code == 200, rb.text
        bid = rb.json()["id"]
        created_bookings.append(bid)
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT action FROM bookings_signal WHERE booking_id = %s ORDER BY created_at",
            (bid,),
        )
        actions = [row[0] for row in cur.fetchall()]
        cur.close()
        assert actions, f"no bookings_signal row found for booking {bid}"
        assert actions[0].upper() in ("INSERT", "I", "CREATE"), f"first signal action was {actions[0]}"

    def test_trigger_emits_signal_on_update_and_delete(self, s, admin, staff1, main_branch, pg_conn):
        d = (date.today() + timedelta(days=461)).isoformat()
        p = _booking_payload(main_branch["id"], "08:00", "09:00", "sig_ud", date_=d)
        rb = s.post(f"{API}/bookings", json=p, headers=hdr(staff1))
        assert rb.status_code == 200, rb.text
        bid = rb.json()["id"]
        # UPDATE
        r2 = s.patch(f"{API}/bookings/{bid}", json={"notes": "trigger-test"}, headers=hdr(staff1))
        assert r2.status_code == 200
        # DELETE (admin)
        r3 = s.delete(f"{API}/bookings/{bid}", headers=hdr(admin))
        assert r3.status_code == 200
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT action FROM bookings_signal WHERE booking_id = %s ORDER BY created_at",
            (bid,),
        )
        actions = [row[0].upper() for row in cur.fetchall()]
        cur.close()
        assert any(a in ("INSERT", "I", "CREATE") for a in actions), f"insert signal missing; got {actions}"
        assert any(a in ("UPDATE", "U") for a in actions), f"update signal missing; got {actions}"
        assert any(a in ("DELETE", "D") for a in actions), f"delete signal missing; got {actions}"


# ---------- Iteration 5: /api/bootstrap (single round-trip) ----------
class TestIter5Bootstrap:
    """Iteration 5: GET /api/bootstrap returns {user, branches, settings, bookings}.
    Bookings are role-scoped: admin sees all branches; manager/user only their own branch.
    /api/auth/me must continue to return the same user payload."""

    def test_bootstrap_requires_auth(self, s):
        r = s.get(f"{API}/bootstrap")
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"

    def test_bootstrap_invalid_token_401(self, s):
        r = s.get(f"{API}/bootstrap", headers={"Authorization": "Bearer not.a.valid.token"})
        assert r.status_code == 401

    def test_bootstrap_admin_shape_and_keys(self, s, admin):
        r = s.get(f"{API}/bootstrap", headers=hdr(admin))
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("user", "branches", "settings", "bookings"):
            assert k in d, f"bootstrap missing key '{k}'; have {list(d.keys())}"
        assert isinstance(d["branches"], list) and len(d["branches"]) >= 2
        assert isinstance(d["bookings"], list)
        assert isinstance(d["settings"], dict) and "id" in d["settings"]

    def test_bootstrap_user_matches_auth_me(self, s, admin):
        rb = s.get(f"{API}/bootstrap", headers=hdr(admin))
        rm = s.get(f"{API}/auth/me", headers=hdr(admin))
        assert rb.status_code == 200 and rm.status_code == 200
        bu = rb.json()["user"]; mu = rm.json()
        # The exact same dict shape — same id/role/username/branch_id
        for k in ("id", "username", "role", "branch_id"):
            assert bu.get(k) == mu.get(k), f"mismatch on '{k}': bootstrap={bu.get(k)}, me={mu.get(k)}"

    def test_bootstrap_admin_sees_all_branches_bookings(self, s, admin, branches):
        r = s.get(f"{API}/bootstrap", headers=hdr(admin))
        assert r.status_code == 200
        bookings = r.json()["bookings"]
        # Admin should see bookings from more than one branch (we have seeded 2+ branches and
        # the test suite creates bookings on Main Hall — but admin scope should still NOT filter).
        branch_ids_in_bookings = {b["branch_id"] for b in bookings}
        # Compare against GET /api/bookings as admin — admin should match (no filter)
        rl = s.get(f"{API}/bookings", headers=hdr(admin))
        assert rl.status_code == 200
        list_ids = {b["id"] for b in rl.json()}
        boot_ids = {b["id"] for b in bookings}
        assert boot_ids == list_ids, (
            f"admin bootstrap bookings differ from GET /api/bookings; "
            f"only in bootstrap: {boot_ids - list_ids}, only in list: {list_ids - boot_ids}"
        )

    def test_bootstrap_manager_scoped_to_own_branch(self, s, manager1):
        r = s.get(f"{API}/bootstrap", headers=hdr(manager1))
        assert r.status_code == 200, r.text
        d = r.json()
        own_bid = manager1["user"]["branch_id"]
        assert own_bid is not None
        bookings = d["bookings"]
        for b in bookings:
            assert b["branch_id"] == own_bid, (
                f"manager bootstrap leaked branch {b['branch_id']} (own={own_bid}) for booking {b['id']}"
            )

    def test_bootstrap_staff_scoped_to_own_branch(self, s, staff1):
        r = s.get(f"{API}/bootstrap", headers=hdr(staff1))
        assert r.status_code == 200, r.text
        d = r.json()
        own_bid = staff1["user"]["branch_id"]
        assert own_bid is not None
        for b in d["bookings"]:
            assert b["branch_id"] == own_bid, (
                f"staff bootstrap leaked branch {b['branch_id']} (own={own_bid})"
            )

    def test_bootstrap_manager2_isolated_from_manager1(self, s, manager1, manager2):
        r1 = s.get(f"{API}/bootstrap", headers=hdr(manager1))
        r2 = s.get(f"{API}/bootstrap", headers=hdr(manager2))
        assert r1.status_code == 200 and r2.status_code == 200
        b1 = {b["id"] for b in r1.json()["bookings"]}
        b2 = {b["id"] for b in r2.json()["bookings"]}
        assert b1.isdisjoint(b2), f"managers across branches see overlapping bookings: {b1 & b2}"

    def test_bootstrap_booking_includes_full_fields(self, s, staff1, main_branch, created_bookings):
        # Create a booking, then verify bootstrap returns it with start_at, end_at, total_amount
        d = (date.today() + timedelta(days=470)).isoformat()
        payload = _booking_payload(main_branch["id"], "11:00", "12:00", "bootShape", date_=d)
        payload["num_people"] = 5
        payload["items"] = [{"item_id": "x", "name": "Test", "price": 100, "quantity": 1}]
        rc = s.post(f"{API}/bookings", json=payload, headers=hdr(staff1))
        assert rc.status_code == 200, rc.text
        bid = rc.json()["id"]
        created_bookings.append(bid)
        rb = s.get(f"{API}/bootstrap", headers=hdr(staff1))
        assert rb.status_code == 200
        match = next((b for b in rb.json()["bookings"] if b["id"] == bid), None)
        assert match is not None, f"booking {bid} not in bootstrap output"
        for k in ("start_at", "end_at", "total_amount", "event_date", "event_time", "event_end_time", "status", "gst_percent"):
            assert k in match, f"bootstrap booking missing '{k}'; keys={list(match.keys())}"
        assert match["start_at"].startswith(d + "T11:00")
        assert match["end_at"].startswith(d + "T12:00")
        assert isinstance(match["total_amount"], (int, float)) and match["total_amount"] > 0

    def test_bootstrap_branches_match_branches_endpoint(self, s, admin):
        # Fetch both back-to-back so any concurrently-created test branches are reflected in both.
        rb = s.get(f"{API}/bootstrap", headers=hdr(admin))
        rl = s.get(f"{API}/branches", headers=hdr(admin))
        assert rb.status_code == 200 and rl.status_code == 200
        bid_boot = {b["id"] for b in rb.json()["branches"]}
        bid_list = {b["id"] for b in rl.json()}
        assert bid_boot == bid_list, f"branches diverge: bootstrap-only={bid_boot - bid_list}, list-only={bid_list - bid_boot}"

    def test_auth_me_still_works(self, s, admin, manager1, staff1):
        for tok in (admin, manager1, staff1):
            r = s.get(f"{API}/auth/me", headers=hdr(tok))
            assert r.status_code == 200, r.text
            assert r.json()["id"] == tok["user"]["id"]


# ---------- Iteration 5: DB indexes assertion ----------
class TestIter5Indexes:
    """Iteration 5: required PG indexes for the perf pass."""

    def _indexes_on(self, pg_conn, table):
        cur = pg_conn.cursor()
        cur.execute(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE schemaname='public' AND tablename=%s",
            (table,),
        )
        rows = cur.fetchall()
        cur.close()
        return rows

    def test_bookings_indexes_present(self, pg_conn):
        rows = self._indexes_on(pg_conn, "bookings")
        defs = " | ".join(d for _, d in rows).lower()
        # branch_id index
        assert "(branch_id)" in defs or "branch_id," in defs, f"bookings.branch_id index missing; defs={defs}"
        # event_date index
        assert "event_date" in defs, f"bookings.event_date index missing; defs={defs}"

    def test_users_branch_id_index_present(self, pg_conn):
        rows = self._indexes_on(pg_conn, "users")
        defs = " | ".join(d for _, d in rows).lower()
        assert "branch_id" in defs, f"users.branch_id index missing; defs={defs}"


# ---------- Teardown ----------
@pytest.fixture(scope="session", autouse=True)
def cleanup(s, admin, created_bookings, created_user_ids, created_branch_ids):
    yield
    h = hdr(admin)
    for bid in created_bookings:
        try: s.delete(f"{API}/bookings/{bid}", headers=h)
        except Exception: pass
    for uid in created_user_ids:
        try: s.delete(f"{API}/users/{uid}", headers=h)
        except Exception: pass
    for brid in created_branch_ids:
        try: s.delete(f"{API}/branches/{brid}", headers=h)
        except Exception: pass
