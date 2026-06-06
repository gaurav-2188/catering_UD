"""UD Catering backend regression tests"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or "https://catering-management-1.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"


# ----------- helpers / fixtures -----------
def _login(username: str, password: str, role: str) -> dict:
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password, "role": role}, timeout=30)
    assert r.status_code == 200, f"Login failed for {username}/{role}: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="session")
def admin_auth():
    return _login("admin@udcatering.com", "admin123", "admin")


@pytest.fixture(scope="session")
def manager_auth():
    return _login("manager1", "manager123", "manager")


@pytest.fixture(scope="session")
def user_auth():
    return _login("staff1", "staff123", "user")


def H(auth):
    return {"Authorization": f"Bearer {auth['token']}"}


@pytest.fixture(scope="session")
def branches(admin_auth):
    r = requests.get(f"{API}/branches", headers=H(admin_auth), timeout=30)
    assert r.status_code == 200
    return r.json()


# ----------- Auth -----------
class TestAuth:
    def test_admin_login(self, admin_auth):
        assert "token" in admin_auth
        assert admin_auth["user"]["role"] == "admin"
        assert admin_auth["user"]["username"] == "admin@udcatering.com"

    def test_manager_login(self, manager_auth):
        assert manager_auth["user"]["role"] == "manager"
        assert manager_auth["user"]["branch_id"]

    def test_user_login(self, user_auth):
        assert user_auth["user"]["role"] == "user"
        assert user_auth["user"]["branch_id"]

    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/login", json={"username": "admin@udcatering.com", "password": "nope", "role": "admin"}, timeout=30)
        assert r.status_code == 401

    def test_auth_me(self, manager_auth):
        r = requests.get(f"{API}/auth/me", headers=H(manager_auth), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["username"] == "manager1"
        assert data["role"] == "manager"

    def test_auth_me_no_token(self):
        r = requests.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 401


# ----------- Branches / Categories / Menu -----------
class TestBranchesMenu:
    def test_list_branches_seeded(self, branches):
        assert isinstance(branches, list)
        assert len(branches) >= 2
        names = [b["name"] for b in branches]
        assert any("Main Hall" in n for n in names)

    def test_categories_per_branch(self, branches, user_auth):
        for b in branches:
            r = requests.get(f"{API}/categories?branch_id={b['id']}", headers=H(user_auth), timeout=30)
            assert r.status_code == 200, r.text
            cats = r.json()
            assert len(cats) >= 6, f"branch {b['name']} has only {len(cats)} categories"

    def test_menu_items_per_branch(self, branches, user_auth):
        for b in branches:
            r = requests.get(f"{API}/menu-items?branch_id={b['id']}", headers=H(user_auth), timeout=30)
            assert r.status_code == 200
            items = r.json()
            assert len(items) >= 5

    def test_admin_create_branch(self, admin_auth):
        name = f"TEST_Branch_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/branches", headers=H(admin_auth), json={"name": name, "address": "test", "gst_percent": 12.0}, timeout=30)
        assert r.status_code == 200, r.text
        new_b = r.json()
        assert new_b["name"] == name
        assert new_b["gst_percent"] == 12.0
        # Cleanup
        requests.delete(f"{API}/branches/{new_b['id']}", headers=H(admin_auth), timeout=30)

    def test_admin_patch_gst(self, admin_auth, branches):
        bid = branches[0]["id"]
        original_gst = branches[0]["gst_percent"]
        new_gst = 9.5
        r = requests.patch(f"{API}/branches/{bid}", headers=H(admin_auth), json={"gst_percent": new_gst}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["gst_percent"] == new_gst
        # restore
        requests.patch(f"{API}/branches/{bid}", headers=H(admin_auth), json={"gst_percent": original_gst}, timeout=30)

    def test_manager_can_only_update_gst(self, manager_auth):
        bid = manager_auth["user"]["branch_id"]
        # Try renaming - should be ignored or rejected; current impl filters out non-gst silently
        r = requests.get(f"{API}/branches", headers=H(manager_auth), timeout=30)
        original = next(b for b in r.json() if b["id"] == bid)
        r2 = requests.patch(f"{API}/branches/{bid}", headers=H(manager_auth), json={"name": "HACKED", "gst_percent": 7.5}, timeout=30)
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["name"] == original["name"], "manager should NOT change name"
        assert body["gst_percent"] == 7.5
        # restore
        requests.patch(f"{API}/branches/{bid}", headers=H(manager_auth), json={"gst_percent": original["gst_percent"]}, timeout=30)

    def test_manager_cannot_update_other_branch(self, manager_auth, branches):
        other = [b for b in branches if b["id"] != manager_auth["user"]["branch_id"]][0]
        r = requests.patch(f"{API}/branches/{other['id']}", headers=H(manager_auth), json={"gst_percent": 99.0}, timeout=30)
        assert r.status_code == 403


# ----------- Users management -----------
class TestUsers:
    def test_manager_create_user_in_branch(self, manager_auth):
        uname = f"test_u_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/users", headers=H(manager_auth), json={"username": uname, "password": "pw123", "role": "user"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["role"] == "user"
        assert data["branch_id"] == manager_auth["user"]["branch_id"]
        # cleanup
        requests.delete(f"{API}/users/{data['id']}", headers=H(manager_auth), timeout=30)

    def test_manager_cannot_create_manager(self, manager_auth):
        r = requests.post(f"{API}/users", headers=H(manager_auth), json={"username": f"m_{uuid.uuid4().hex[:6]}", "password": "pw", "role": "manager"}, timeout=30)
        assert r.status_code == 403

    def test_manager_cannot_create_admin(self, manager_auth):
        r = requests.post(f"{API}/users", headers=H(manager_auth), json={"username": f"a_{uuid.uuid4().hex[:6]}", "password": "pw", "role": "admin"}, timeout=30)
        assert r.status_code == 403

    def test_user_cannot_list_users(self, user_auth):
        r = requests.get(f"{API}/users", headers=H(user_auth), timeout=30)
        assert r.status_code == 403


# ----------- Bookings -----------
@pytest.fixture(scope="class")
def sample_items(user_auth):
    bid = user_auth["user"]["branch_id"]
    r = requests.get(f"{API}/menu-items?branch_id={bid}", headers=H(user_auth), timeout=30)
    items = r.json()
    return [{"item_id": items[0]["id"], "name": items[0]["name"], "price": items[0]["price"], "quantity": 10}]


def _future_date_str(offset_days=30):
    return (datetime.now(timezone.utc).date() + timedelta(days=offset_days)).isoformat()


class TestBookings:
    created_ids = []

    def test_create_booking(self, user_auth, sample_items):
        body = {
            "branch_id": user_auth["user"]["branch_id"],
            "customer_name": "TEST_Customer",
            "phone": "9999999999",
            "num_people": 50,
            "venue_type": "in_house",
            "venue_address": "",
            "event_date": _future_date_str(30),
            "event_time": "18:00",
            "items": sample_items,
            "discount_amount": 0,
            "discount_percent": 0,
            "transportation_cost": 200,
            "advance_paid": 1000,
            "notes": "test"
        }
        r = requests.post(f"{API}/bookings", headers=H(user_auth), json=body, timeout=30)
        assert r.status_code == 200, r.text
        bk = r.json()
        TestBookings.created_ids.append(bk["id"])
        assert bk["customer_name"] == "TEST_Customer"
        assert bk["gst_percent"] in (18.0, 18)  # stamped from branch
        assert bk["branch_id"] == user_auth["user"]["branch_id"]
        assert bk["status"] == "booked"

    def test_create_booking_conflict_returns_409(self, user_auth, sample_items):
        date = _future_date_str(31)
        body = {
            "branch_id": user_auth["user"]["branch_id"],
            "customer_name": "TEST_C1", "phone": "1", "num_people": 10,
            "venue_type": "in_house", "event_date": date, "event_time": "19:00",
            "items": sample_items
        }
        r1 = requests.post(f"{API}/bookings", headers=H(user_auth), json=body, timeout=30)
        assert r1.status_code == 200
        TestBookings.created_ids.append(r1.json()["id"])

        body2 = dict(body, customer_name="TEST_C2")
        r2 = requests.post(f"{API}/bookings", headers=H(user_auth), json=body2, timeout=30)
        assert r2.status_code == 409, r2.text
        detail = r2.json().get("detail")
        assert isinstance(detail, dict)
        assert detail.get("code") == "TIME_CONFLICT"
        assert detail.get("existing_id") == r1.json()["id"]

    def test_ignore_conflict_creates_booking(self, user_auth, sample_items):
        date = _future_date_str(32)
        body = {
            "branch_id": user_auth["user"]["branch_id"],
            "customer_name": "TEST_F1", "phone": "1", "num_people": 10,
            "venue_type": "in_house", "event_date": date, "event_time": "20:00",
            "items": sample_items
        }
        r1 = requests.post(f"{API}/bookings", headers=H(user_auth), json=body, timeout=30)
        assert r1.status_code == 200
        TestBookings.created_ids.append(r1.json()["id"])

        body2 = dict(body, customer_name="TEST_F2", ignore_conflict=True)
        r2 = requests.post(f"{API}/bookings", headers=H(user_auth), json=body2, timeout=30)
        assert r2.status_code == 200, r2.text
        TestBookings.created_ids.append(r2.json()["id"])

    def test_patch_booking_status(self, user_auth, sample_items):
        body = {
            "branch_id": user_auth["user"]["branch_id"],
            "customer_name": "TEST_Patch", "phone": "1", "num_people": 5,
            "venue_type": "outside", "event_date": _future_date_str(33), "event_time": "10:00",
            "items": sample_items
        }
        r = requests.post(f"{API}/bookings", headers=H(user_auth), json=body, timeout=30)
        bid = r.json()["id"]
        TestBookings.created_ids.append(bid)
        r2 = requests.patch(f"{API}/bookings/{bid}", headers=H(user_auth), json={"status": "completed"}, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["status"] == "completed"
        r3 = requests.patch(f"{API}/bookings/{bid}", headers=H(user_auth), json={"status": "cancelled"}, timeout=30)
        assert r3.status_code == 200
        assert r3.json()["status"] == "cancelled"

    def test_delete_booking(self, user_auth, sample_items):
        body = {
            "branch_id": user_auth["user"]["branch_id"],
            "customer_name": "TEST_Del", "phone": "1", "num_people": 5,
            "venue_type": "in_house", "event_date": _future_date_str(34), "event_time": "11:00",
            "items": sample_items
        }
        r = requests.post(f"{API}/bookings", headers=H(user_auth), json=body, timeout=30)
        bid = r.json()["id"]
        rd = requests.delete(f"{API}/bookings/{bid}", headers=H(user_auth), timeout=30)
        assert rd.status_code == 200
        # verify gone
        r2 = requests.patch(f"{API}/bookings/{bid}", headers=H(user_auth), json={"status": "completed"}, timeout=30)
        assert r2.status_code == 404

    def test_cleanup(self, user_auth):
        for bid in TestBookings.created_ids:
            requests.delete(f"{API}/bookings/{bid}", headers=H(user_auth), timeout=30)


# ----------- Analytics, Weather, Settings -----------
class TestMisc:
    def test_analytics_summary(self, manager_auth):
        r = requests.get(f"{API}/analytics/summary", headers=H(manager_auth), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ["daily", "weekly", "monthly", "yearly", "daily_series", "monthly_series"]:
            assert k in data
        for k in ["daily", "weekly", "monthly", "yearly"]:
            assert "bookings" in data[k] and "sales" in data[k]
        assert isinstance(data["daily_series"], list)

    def test_weather(self, user_auth):
        r = requests.get(f"{API}/weather", headers=H(user_auth), timeout=30)
        assert r.status_code == 200
        forecast = r.json()["forecast"]
        assert len(forecast) == 5
        for f in forecast:
            for k in ("date", "condition", "severity"):
                assert k in f

    def test_settings_update_admin(self, admin_auth):
        logo = "data:image/png;base64,AAAA"
        r = requests.patch(f"{API}/settings", headers=H(admin_auth), json={"id": "global", "company_logo": logo}, timeout=30)
        assert r.status_code == 200
        assert r.json()["company_logo"] == logo
        # reset
        requests.patch(f"{API}/settings", headers=H(admin_auth), json={"id": "global", "company_logo": ""}, timeout=30)

    def test_settings_update_user_forbidden(self, user_auth):
        r = requests.patch(f"{API}/settings", headers=H(user_auth), json={"id": "global", "company_logo": "x"}, timeout=30)
        assert r.status_code == 403
