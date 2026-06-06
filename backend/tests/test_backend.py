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
