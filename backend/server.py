from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal
import re

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, and_, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, model_validator, field_validator

from database import AsyncSessionLocal, get_db
import models as m

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"

app = FastAPI()
api = APIRouter(prefix="/api")


# ---------- Helpers ----------
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def make_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id, "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def _user_dict(u: m.User) -> dict:
    return {
        "id": u.id, "username": u.username, "role": u.role,
        "branch_id": u.branch_id, "created_at": u.created_at.isoformat() if u.created_at else None,
    }


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    res = await db.execute(select(m.User).where(m.User.id == payload["sub"]))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return _user_dict(user)


def require_role(*roles: str):
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return dep


def _booking_dict(b: m.Booking) -> dict:
    return {
        "id": b.id, "branch_id": b.branch_id,
        "customer_name": b.customer_name, "phone": b.phone, "num_people": b.num_people,
        "venue_type": b.venue_type, "venue_address": b.venue_address,
        "event_date": b.event_date, "event_time": b.event_time, "event_end_time": b.event_end_time,
        "start_at": b.start_at.isoformat() if b.start_at else None,
        "end_at": b.end_at.isoformat() if b.end_at else None,
        "items": b.items, "discount_amount": float(b.discount_amount or 0),
        "discount_percent": float(b.discount_percent or 0),
        "transportation_cost": float(b.transportation_cost or 0),
        "advance_paid": float(b.advance_paid or 0), "gst_percent": float(b.gst_percent or 18),
        "notes": b.notes, "status": b.status, "created_by": b.created_by,
        "total_amount": float(b.total_amount or 0),
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


def _branch_dict(b: m.Branch) -> dict:
    return {
        "id": b.id, "name": b.name, "address": b.address,
        "gst_percent": float(b.gst_percent or 18),
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


# ---------- Models ----------
Role = Literal["admin", "manager", "user"]


class LoginInput(BaseModel):
    username: str
    password: str
    role: Role


class UserCreate(BaseModel):
    username: str
    password: str
    role: Role
    branch_id: Optional[str] = None


class BranchCreate(BaseModel):
    name: str
    address: str = ""
    gst_percent: float = 18.0


class BranchUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    gst_percent: Optional[float] = None


class CategoryCreate(BaseModel):
    branch_id: str
    name: str
    sort_order: int = 0


class MenuItemCreate(BaseModel):
    branch_id: str
    category_id: str
    name: str
    price: float


class BookingItem(BaseModel):
    item_id: str
    name: str
    price: float
    quantity: int = 1


_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_YMD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


def _validate_hhmm(v: str) -> str:
    if not _HHMM_RE.match(v or ""):
        raise ValueError("must be HH:MM (24h)")
    return v


def _validate_ymd(v: str) -> str:
    if not _YMD_RE.match(v or ""):
        raise ValueError("must be YYYY-MM-DD")
    return v


class BookingCreate(BaseModel):
    branch_id: str
    customer_name: str
    phone: str
    num_people: int
    venue_type: Literal["in_house", "outside"]
    venue_address: str = ""
    event_date: str
    event_time: str
    event_end_time: str
    items: List[BookingItem]
    discount_amount: float = 0
    discount_percent: float = 0
    transportation_cost: float = 0
    advance_paid: float = 0
    notes: str = ""
    ignore_conflict: bool = False

    _v_date = field_validator("event_date")(lambda cls, v: _validate_ymd(v))
    _v_time = field_validator("event_time", "event_end_time")(lambda cls, v: _validate_hhmm(v))


class BookingUpdate(BaseModel):
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    num_people: Optional[int] = None
    venue_type: Optional[Literal["in_house", "outside"]] = None
    venue_address: Optional[str] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    event_end_time: Optional[str] = None
    items: Optional[List[BookingItem]] = None
    discount_amount: Optional[float] = None
    discount_percent: Optional[float] = None
    transportation_cost: Optional[float] = None
    advance_paid: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[Literal["booked", "completed", "cancelled"]] = None
    ignore_conflict: bool = False

    @field_validator("event_date")
    @classmethod
    def _vd(cls, v):
        return _validate_ymd(v) if v is not None else v

    @field_validator("event_time", "event_end_time")
    @classmethod
    def _vt(cls, v):
        return _validate_hhmm(v) if v is not None else v


class SettingsBody(BaseModel):
    id: str = "global"
    company_logo: str = ""


# ---------- Auth ----------
@api.post("/auth/login")
async def login(body: LoginInput, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(m.User).where(m.User.username == body.username.lower(), m.User.role == body.role)
    )
    user = res.scalar_one_or_none()
    if not user or not verify_pw(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": make_token(user.id, user.role), "user": _user_dict(user)}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.get("/bootstrap")
async def bootstrap(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Single round-trip used on app load — returns the authenticated user
    plus every initial blob (branches, settings, role-scoped bookings) so the
    client can render the calendar without a request waterfall."""
    # Parallel-equivalent: 3 small queries on the same connection
    branches_res = await db.execute(select(m.Branch).order_by(m.Branch.name))
    branches = [_branch_dict(b) for b in branches_res.scalars().all()]

    settings_res = await db.execute(select(m.Settings).where(m.Settings.id == "global"))
    s = settings_res.scalar_one_or_none()
    if not s:
        s = m.Settings(id="global", company_logo="")
        db.add(s); await db.commit(); await db.refresh(s)
    settings_dict = {"id": s.id, "company_logo": s.company_logo or ""}

    bq = select(m.Booking)
    if user["role"] in ("user", "manager"):
        bq = bq.where(m.Booking.branch_id == user.get("branch_id"))
    bres = await db.execute(bq.order_by(m.Booking.event_date.desc(), m.Booking.event_time))
    bookings = [_booking_dict(b) for b in bres.scalars().all()]

    return {"user": user, "branches": branches, "settings": settings_dict, "bookings": bookings}


# ---------- Branches ----------
@api.get("/branches")
async def list_branches(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(m.Branch).order_by(m.Branch.name))
    return [_branch_dict(b) for b in res.scalars().all()]


@api.post("/branches")
async def create_branch(body: BranchCreate, user: dict = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    b = m.Branch(id=str(uuid.uuid4()), name=body.name, address=body.address, gst_percent=body.gst_percent)
    db.add(b); await db.commit(); await db.refresh(b)
    return _branch_dict(b)


@api.patch("/branches/{branch_id}")
async def update_branch(branch_id: str, body: BranchUpdate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(m.Branch).where(m.Branch.id == branch_id))
    branch = res.scalar_one_or_none()
    if not branch:
        raise HTTPException(404, "Branch not found")
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if user["role"] == "manager":
        if user.get("branch_id") != branch_id:
            raise HTTPException(403, "Not your branch")
        update = {k: v for k, v in update.items() if k == "gst_percent"}
    elif user["role"] != "admin":
        raise HTTPException(403, "Forbidden")
    for k, v in update.items():
        setattr(branch, k, v)
    await db.commit(); await db.refresh(branch)
    return _branch_dict(branch)


@api.delete("/branches/{branch_id}")
async def delete_branch(branch_id: str, user: dict = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(m.Branch).where(m.Branch.id == branch_id))
    branch = res.scalar_one_or_none()
    if branch:
        await db.delete(branch); await db.commit()
    return {"ok": True}


# ---------- Users ----------
@api.get("/users")
async def list_users(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user["role"] == "user":
        raise HTTPException(403, "Forbidden")
    q = select(m.User)
    if user["role"] == "manager":
        q = q.where(m.User.branch_id == user.get("branch_id"))
    res = await db.execute(q.order_by(m.User.role, m.User.username))
    return [_user_dict(u) for u in res.scalars().all()]


@api.post("/users")
async def create_user(body: UserCreate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user["role"] == "user":
        raise HTTPException(403, "Forbidden")
    if user["role"] == "manager":
        if body.role != "user":
            raise HTTPException(403, "Managers can only create User accounts")
        body.branch_id = user.get("branch_id")
    username = body.username.lower().strip()
    exists = await db.execute(select(m.User).where(m.User.username == username, m.User.role == body.role))
    if exists.scalar_one_or_none():
        raise HTTPException(400, "Username already exists for this role")
    new_user = m.User(
        id=str(uuid.uuid4()), username=username, password_hash=hash_pw(body.password),
        role=body.role, branch_id=body.branch_id,
    )
    db.add(new_user); await db.commit(); await db.refresh(new_user)
    return _user_dict(new_user)


@api.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user["role"] == "user":
        raise HTTPException(403, "Forbidden")
    res = await db.execute(select(m.User).where(m.User.id == user_id))
    target = res.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "Not found")
    if user["role"] == "manager":
        if target.role != "user" or target.branch_id != user.get("branch_id"):
            raise HTTPException(403, "Forbidden")
    if target.id == user["id"]:
        raise HTTPException(400, "Cannot delete self")
    await db.delete(target); await db.commit()
    return {"ok": True}


# ---------- Categories ----------
@api.get("/categories")
async def list_categories(branch_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(m.Category).where(m.Category.branch_id == branch_id).order_by(m.Category.sort_order)
    )
    return [{"id": c.id, "branch_id": c.branch_id, "name": c.name, "sort_order": c.sort_order} for c in res.scalars().all()]


@api.post("/categories")
async def create_category(body: CategoryCreate, user: dict = Depends(require_role("admin", "manager")), db: AsyncSession = Depends(get_db)):
    if user["role"] == "manager" and user.get("branch_id") != body.branch_id:
        raise HTTPException(403, "Not your branch")
    c = m.Category(id=str(uuid.uuid4()), branch_id=body.branch_id, name=body.name, sort_order=body.sort_order)
    db.add(c); await db.commit(); await db.refresh(c)
    return {"id": c.id, "branch_id": c.branch_id, "name": c.name, "sort_order": c.sort_order}


@api.delete("/categories/{category_id}")
async def delete_category(category_id: str, user: dict = Depends(require_role("admin", "manager")), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(m.Category).where(m.Category.id == category_id))
    cat = res.scalar_one_or_none()
    if not cat:
        raise HTTPException(404, "Not found")
    if user["role"] == "manager" and user.get("branch_id") != cat.branch_id:
        raise HTTPException(403, "Not your branch")
    await db.delete(cat); await db.commit()
    return {"ok": True}


# ---------- Menu Items ----------
@api.get("/menu-items")
async def list_menu_items(branch_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(m.MenuItem).where(m.MenuItem.branch_id == branch_id))
    return [{"id": x.id, "branch_id": x.branch_id, "category_id": x.category_id, "name": x.name, "price": float(x.price)} for x in res.scalars().all()]


@api.post("/menu-items")
async def create_menu_item(body: MenuItemCreate, user: dict = Depends(require_role("admin", "manager")), db: AsyncSession = Depends(get_db)):
    if user["role"] == "manager" and user.get("branch_id") != body.branch_id:
        raise HTTPException(403, "Not your branch")
    mi = m.MenuItem(id=str(uuid.uuid4()), **body.model_dump())
    db.add(mi); await db.commit(); await db.refresh(mi)
    return {"id": mi.id, "branch_id": mi.branch_id, "category_id": mi.category_id, "name": mi.name, "price": float(mi.price)}


@api.patch("/menu-items/{item_id}")
async def update_menu_item(item_id: str, body: MenuItemCreate, user: dict = Depends(require_role("admin", "manager")), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(m.MenuItem).where(m.MenuItem.id == item_id))
    mi = res.scalar_one_or_none()
    if not mi:
        raise HTTPException(404, "Not found")
    if user["role"] == "manager" and user.get("branch_id") != mi.branch_id:
        raise HTTPException(403, "Not your branch")
    for k, v in body.model_dump().items():
        setattr(mi, k, v)
    await db.commit(); await db.refresh(mi)
    return {"id": mi.id, "branch_id": mi.branch_id, "category_id": mi.category_id, "name": mi.name, "price": float(mi.price)}


@api.delete("/menu-items/{item_id}")
async def delete_menu_item(item_id: str, user: dict = Depends(require_role("admin", "manager")), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(m.MenuItem).where(m.MenuItem.id == item_id))
    mi = res.scalar_one_or_none()
    if not mi:
        raise HTTPException(404, "Not found")
    if user["role"] == "manager" and user.get("branch_id") != mi.branch_id:
        raise HTTPException(403, "Not your branch")
    await db.delete(mi); await db.commit()
    return {"ok": True}


# ---------- Bookings ----------
def _compute_total_amount(items, num_people: int, discount_amount: float, discount_percent: float, transportation_cost: float, gst_percent: float) -> float:
    """Per-person pricing: subtotal = sum(item.price) × num_people."""
    per_person_rate = sum(float(it["price"] if isinstance(it, dict) else it.price) for it in items)
    subtotal = per_person_rate * (num_people or 0)
    discount = (discount_amount or 0) + subtotal * (discount_percent or 0) / 100
    taxable = max(0.0, subtotal - discount)
    gst = taxable * (gst_percent or 0) / 100
    return taxable + gst + (transportation_cost or 0)


def _compute_range(event_date: str, start_str: str, end_str: str):
    """Return (start_at, end_at) datetimes. If end <= start the event is treated
    as overnight (end is next day)."""
    start_at = datetime.strptime(f"{event_date} {start_str}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    end_at = datetime.strptime(f"{event_date} {end_str}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    if end_at <= start_at:
        end_at += timedelta(days=1)
    return start_at, end_at


async def _find_conflict(db: AsyncSession, branch_id: str, start_at: datetime, end_at: datetime, exclude_id: Optional[str] = None) -> Optional[m.Booking]:
    # Range overlap on absolute timestamps — handles overnight events correctly.
    q = select(m.Booking).where(
        m.Booking.branch_id == branch_id,
        m.Booking.status != "cancelled",
        m.Booking.start_at < end_at,
        m.Booking.end_at > start_at,
    )
    if exclude_id:
        q = q.where(m.Booking.id != exclude_id)
    res = await db.execute(q.limit(1))
    return res.scalar_one_or_none()


@api.get("/bookings")
async def list_bookings(branch_id: Optional[str] = None, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    q = select(m.Booking)
    if user["role"] in ("user", "manager"):
        q = q.where(m.Booking.branch_id == user.get("branch_id"))
    elif branch_id:
        q = q.where(m.Booking.branch_id == branch_id)
    res = await db.execute(q.order_by(m.Booking.event_date.desc(), m.Booking.event_time))
    return [_booking_dict(b) for b in res.scalars().all()]


@api.post("/bookings")
async def create_booking(body: BookingCreate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user["role"] != "admin" and user.get("branch_id") != body.branch_id:
        raise HTTPException(403, "Not your branch")
    new_start, new_end = _compute_range(body.event_date, body.event_time, body.event_end_time)
    if not body.ignore_conflict:
        existing = await _find_conflict(db, body.branch_id, new_start, new_end)
        if existing:
            raise HTTPException(status_code=409, detail={"code": "TIME_CONFLICT", "existing_id": existing.id})
    br = await db.execute(select(m.Branch).where(m.Branch.id == body.branch_id))
    branch = br.scalar_one_or_none()
    gst = float(branch.gst_percent) if branch else 18.0
    bk = m.Booking(
        id=str(uuid.uuid4()), branch_id=body.branch_id,
        customer_name=body.customer_name, phone=body.phone, num_people=body.num_people,
        venue_type=body.venue_type, venue_address=body.venue_address,
        event_date=body.event_date, event_time=body.event_time, event_end_time=body.event_end_time,
        start_at=new_start, end_at=new_end,
        items=[i.model_dump() for i in body.items],
        discount_amount=body.discount_amount, discount_percent=body.discount_percent,
        transportation_cost=body.transportation_cost, advance_paid=body.advance_paid,
        notes=body.notes, gst_percent=gst, created_by=user["id"], status="booked",
        total_amount=_compute_total_amount(
            body.items, body.num_people, body.discount_amount, body.discount_percent,
            body.transportation_cost, gst,
        ),
    )
    db.add(bk); await db.commit(); await db.refresh(bk)
    return _booking_dict(bk)


@api.patch("/bookings/{booking_id}")
async def update_booking(booking_id: str, body: BookingUpdate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(m.Booking).where(m.Booking.id == booking_id))
    bk = res.scalar_one_or_none()
    if not bk:
        raise HTTPException(404, "Not found")
    if user["role"] != "admin" and user.get("branch_id") != bk.branch_id:
        raise HTTPException(403, "Forbidden")
    update = {k: v for k, v in body.model_dump().items() if v is not None and k != "ignore_conflict"}
    new_date = update.get("event_date", bk.event_date)
    new_start_str = update.get("event_time", bk.event_time)
    new_end_str = update.get("event_end_time", bk.event_end_time)
    time_changed = new_date != bk.event_date or new_start_str != bk.event_time or new_end_str != bk.event_end_time
    if time_changed:
        new_start, new_end = _compute_range(new_date, new_start_str, new_end_str)
        if not body.ignore_conflict:
            existing = await _find_conflict(db, bk.branch_id, new_start, new_end, exclude_id=booking_id)
            if existing:
                raise HTTPException(status_code=409, detail={"code": "TIME_CONFLICT", "existing_id": existing.id})
        update["start_at"] = new_start
        update["end_at"] = new_end
    if "items" in update:
        update["items"] = [i if isinstance(i, dict) else i.model_dump() for i in update["items"]]
    # Only touch the cached total_amount when a price-affecting field actually changed.
    # Status-only flips (Mark Completed / Cancel) become a single-column UPDATE.
    _price_keys = {"items", "num_people", "discount_amount", "discount_percent", "transportation_cost", "gst_percent"}
    needs_total_refresh = bool(_price_keys & set(update.keys()))
    for k, v in update.items():
        setattr(bk, k, v)
    if needs_total_refresh:
        bk.total_amount = _compute_total_amount(
            bk.items, bk.num_people, float(bk.discount_amount or 0), float(bk.discount_percent or 0),
            float(bk.transportation_cost or 0), float(bk.gst_percent or 18),
        )
    await db.commit(); await db.refresh(bk)
    return _booking_dict(bk)


@api.delete("/bookings/{booking_id}")
async def delete_booking(booking_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(m.Booking).where(m.Booking.id == booking_id))
    bk = res.scalar_one_or_none()
    if not bk:
        raise HTTPException(404, "Not found")
    if user["role"] != "admin" and user.get("branch_id") != bk.branch_id:
        raise HTTPException(403, "Forbidden")
    await db.delete(bk); await db.commit()
    return {"ok": True}


# ---------- Settings ----------
@api.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(m.Settings).where(m.Settings.id == "global"))
    s = res.scalar_one_or_none()
    if not s:
        s = m.Settings(id="global", company_logo="")
        db.add(s); await db.commit(); await db.refresh(s)
    return {"id": s.id, "company_logo": s.company_logo or ""}


@api.patch("/settings")
async def update_settings(body: SettingsBody, user: dict = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(m.Settings).where(m.Settings.id == "global"))
    s = res.scalar_one_or_none()
    if not s:
        s = m.Settings(id="global", company_logo=body.company_logo)
        db.add(s)
    else:
        s.company_logo = body.company_logo
    await db.commit(); await db.refresh(s)
    return {"id": s.id, "company_logo": s.company_logo or ""}


# ---------- Analytics ----------
@api.get("/analytics/summary")
async def analytics_summary(branch_id: Optional[str] = None, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user["role"] != "admin":
        branch_id = user.get("branch_id")

    today = datetime.now(timezone.utc).date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    base_filter = "WHERE b.status != 'cancelled'"
    params = {}
    if branch_id:
        base_filter += " AND b.branch_id = :branch_id"
        params["branch_id"] = branch_id

    from sqlalchemy import text

    async def bucket(date_predicate: str, p: dict):
        sql = f"""
            SELECT COUNT(*) AS bookings, COALESCE(SUM(b.total_amount), 0) AS sales
            FROM bookings b
            {base_filter} AND {date_predicate}
        """
        r = await db.execute(text(sql), {**params, **p})
        row = r.first()
        return {"bookings": int(row.bookings or 0), "sales": float(row.sales or 0)}

    daily = await bucket("b.event_date = :d", {"d": today.isoformat()})
    weekly = await bucket("b.event_date >= :d", {"d": week_start.isoformat()})
    monthly = await bucket("b.event_date >= :d", {"d": month_start.isoformat()})
    yearly = await bucket("b.event_date >= :d", {"d": year_start.isoformat()})

    # Daily series — last 30 days
    sql_daily = f"""
        SELECT b.event_date AS date, COUNT(*) AS bookings, COALESCE(SUM(b.total_amount), 0) AS sales
        FROM bookings b
        {base_filter} AND b.event_date >= :since
        GROUP BY b.event_date
        ORDER BY b.event_date
    """
    r = await db.execute(text(sql_daily), {**params, "since": (today - timedelta(days=29)).isoformat()})
    daily_series = [{"date": row.date, "bookings": int(row.bookings), "sales": float(row.sales)} for row in r]

    # Monthly series — last 12 months
    sql_monthly = f"""
        SELECT substring(b.event_date, 1, 7) AS month,
               COUNT(*) AS bookings, COALESCE(SUM(b.total_amount), 0) AS sales
        FROM bookings b
        {base_filter} AND b.event_date >= :since
        GROUP BY 1
        ORDER BY 1
    """
    r = await db.execute(text(sql_monthly), {**params, "since": (today - timedelta(days=365)).isoformat()})
    monthly_series = [{"month": row.month, "bookings": int(row.bookings), "sales": float(row.sales)} for row in r]

    return {
        "daily": daily, "weekly": weekly, "monthly": monthly, "yearly": yearly,
        "daily_series": daily_series, "monthly_series": monthly_series,
    }


# ---------- Seed ----------
async def seed():
    async with AsyncSessionLocal() as db:
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@udcatering.com").lower()
        admin_pw = os.environ.get("ADMIN_PASSWORD", "admin123")
        res = await db.execute(select(m.User).where(m.User.username == admin_email, m.User.role == "admin"))
        if not res.scalar_one_or_none():
            db.add(m.User(id=str(uuid.uuid4()), username=admin_email, password_hash=hash_pw(admin_pw),
                          role="admin", branch_id=None))
            await db.commit()

        res = await db.execute(select(func.count()).select_from(m.Branch))
        count = res.scalar_one()
        if count == 0:
            seed_branches = [
                {"name": "UD Catering — Main Hall", "address": "12 MG Road, Bengaluru, KA", "gst_percent": 18.0},
                {"name": "UD Catering — Downtown", "address": "45 Brigade Road, Bengaluru, KA", "gst_percent": 18.0},
            ]
            for bdata in seed_branches:
                db.add(m.Branch(id=str(uuid.uuid4()), **bdata))
            await db.commit()

            sample_menu = {
                "Appetizers": [("Paneer Tikka", 280), ("Veg Manchurian", 220), ("Chicken 65", 320), ("Hara Bhara Kebab", 240)],
                "Main Course": [("Butter Chicken", 380), ("Paneer Butter Masala", 320), ("Dal Makhani", 260), ("Veg Biryani", 280)],
                "Breads": [("Butter Naan", 50), ("Tandoori Roti", 30), ("Lachha Paratha", 60)],
                "Rice & Pulao": [("Jeera Rice", 180), ("Hyderabadi Biryani", 350)],
                "Desserts": [("Gulab Jamun", 80), ("Rasmalai", 120), ("Gajar Halwa", 140)],
                "Beverages": [("Masala Chai", 40), ("Sweet Lassi", 80), ("Fresh Lime Soda", 60)],
            }
            res = await db.execute(select(m.Branch).order_by(m.Branch.name))
            branches = res.scalars().all()
            for i, br in enumerate(branches, start=1):
                db.add(m.User(id=str(uuid.uuid4()), username=f"manager{i}", password_hash=hash_pw("manager123"),
                              role="manager", branch_id=br.id))
                db.add(m.User(id=str(uuid.uuid4()), username=f"staff{i}", password_hash=hash_pw("staff123"),
                              role="user", branch_id=br.id))
                for sort_idx, (cat_name, items) in enumerate(sample_menu.items()):
                    c = m.Category(id=str(uuid.uuid4()), branch_id=br.id, name=cat_name, sort_order=sort_idx)
                    db.add(c); await db.flush()
                    for name, price in items:
                        db.add(m.MenuItem(id=str(uuid.uuid4()), branch_id=br.id, category_id=c.id, name=name, price=price))
            await db.commit()

        res = await db.execute(select(m.Settings).where(m.Settings.id == "global"))
        if not res.scalar_one_or_none():
            db.add(m.Settings(id="global", company_logo=""))
            await db.commit()


@app.on_event("startup")
async def on_start():
    await seed()


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
