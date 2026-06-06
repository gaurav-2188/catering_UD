from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

# ---------- DB ----------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = "HS256"

app = FastAPI()
api = APIRouter(prefix="/api")

# ---------- Helpers ----------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

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

async def get_current_user(request: Request) -> dict:
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
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_role(*roles: str):
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return dep

# ---------- Models ----------
Role = Literal["admin", "manager", "user"]

class LoginInput(BaseModel):
    username: str
    password: str
    role: Role

class UserPublic(BaseModel):
    id: str
    username: str
    role: Role
    branch_id: Optional[str] = None
    created_at: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: Role
    branch_id: Optional[str] = None

class Branch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    address: str = ""
    gst_percent: float = 18.0
    created_at: str = Field(default_factory=now_iso)

class BranchCreate(BaseModel):
    name: str
    address: str = ""
    gst_percent: float = 18.0

class BranchUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    gst_percent: Optional[float] = None

class Category(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    branch_id: str
    name: str
    sort_order: int = 0

class CategoryCreate(BaseModel):
    branch_id: str
    name: str
    sort_order: int = 0

class MenuItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    branch_id: str
    category_id: str
    name: str
    price: float

class MenuItemCreate(BaseModel):
    branch_id: str
    category_id: str
    name: str
    price: float

class BookingItem(BaseModel):
    item_id: str
    name: str
    price: float
    quantity: int

class Booking(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    branch_id: str
    customer_name: str
    phone: str
    num_people: int
    venue_type: Literal["in_house", "outside"]
    venue_address: str = ""
    event_date: str  # YYYY-MM-DD
    event_time: str  # HH:MM (start)
    event_end_time: str  # HH:MM (end)
    items: List[BookingItem]
    discount_amount: float = 0
    discount_percent: float = 0
    transportation_cost: float = 0
    advance_paid: float = 0
    gst_percent: float = 18.0
    notes: str = ""
    status: Literal["booked", "completed", "cancelled"] = "booked"
    created_by: str
    created_at: str = Field(default_factory=now_iso)

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

class Settings(BaseModel):
    id: str = "global"
    company_logo: str = ""  # base64 data URL

# ---------- Auth ----------
@api.post("/auth/login")
async def login(body: LoginInput):
    user = await db.users.find_one({"username": body.username.lower(), "role": body.role})
    if not user or not verify_pw(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = make_token(user["id"], user["role"])
    return {
        "token": token,
        "user": {
            "id": user["id"], "username": user["username"], "role": user["role"],
            "branch_id": user.get("branch_id"), "created_at": user["created_at"],
        }
    }

@api.get("/auth/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return UserPublic(**user)

# ---------- Branches ----------
@api.get("/branches")
async def list_branches(user: dict = Depends(get_current_user)):
    docs = await db.branches.find({}, {"_id": 0}).to_list(1000)
    return docs

@api.post("/branches")
async def create_branch(body: BranchCreate, user: dict = Depends(require_role("admin"))):
    b = Branch(**body.model_dump())
    await db.branches.insert_one(b.model_dump())
    return b

@api.patch("/branches/{branch_id}")
async def update_branch(branch_id: str, body: BranchUpdate, user: dict = Depends(get_current_user)):
    # Admin can edit anything, manager can only edit gst for their branch
    branch = await db.branches.find_one({"id": branch_id}, {"_id": 0})
    if not branch:
        raise HTTPException(404, "Branch not found")
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if user["role"] == "manager":
        if user.get("branch_id") != branch_id:
            raise HTTPException(403, "Not your branch")
        update = {k: v for k, v in update.items() if k == "gst_percent"}
    elif user["role"] != "admin":
        raise HTTPException(403, "Forbidden")
    if update:
        await db.branches.update_one({"id": branch_id}, {"$set": update})
    return await db.branches.find_one({"id": branch_id}, {"_id": 0})

@api.delete("/branches/{branch_id}")
async def delete_branch(branch_id: str, user: dict = Depends(require_role("admin"))):
    await db.branches.delete_one({"id": branch_id})
    await db.categories.delete_many({"branch_id": branch_id})
    await db.menu_items.delete_many({"branch_id": branch_id})
    await db.bookings.delete_many({"branch_id": branch_id})
    return {"ok": True}

# ---------- Users (staff management) ----------
@api.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    q = {}
    if user["role"] == "manager":
        q = {"branch_id": user.get("branch_id")}
    elif user["role"] == "user":
        raise HTTPException(403, "Forbidden")
    docs = await db.users.find(q, {"_id": 0, "password_hash": 0}).to_list(1000)
    return docs

@api.post("/users")
async def create_user(body: UserCreate, user: dict = Depends(get_current_user)):
    if user["role"] == "user":
        raise HTTPException(403, "Forbidden")
    # Manager can only create users in their branch
    if user["role"] == "manager":
        if body.role != "user":
            raise HTTPException(403, "Managers can only create User accounts")
        body.branch_id = user.get("branch_id")
    username = body.username.lower().strip()
    if await db.users.find_one({"username": username, "role": body.role}):
        raise HTTPException(400, "Username already exists for this role")
    doc = {
        "id": str(uuid.uuid4()),
        "username": username,
        "password_hash": hash_pw(body.password),
        "role": body.role,
        "branch_id": body.branch_id,
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    return {k: v for k, v in doc.items() if k not in ("password_hash", "_id")}

@api.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(get_current_user)):
    if user["role"] == "user":
        raise HTTPException(403, "Forbidden")
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "Not found")
    if user["role"] == "manager":
        if target["role"] != "user" or target.get("branch_id") != user.get("branch_id"):
            raise HTTPException(403, "Forbidden")
    if target["id"] == user["id"]:
        raise HTTPException(400, "Cannot delete self")
    await db.users.delete_one({"id": user_id})
    return {"ok": True}

# ---------- Categories ----------
@api.get("/categories")
async def list_categories(branch_id: str, user: dict = Depends(get_current_user)):
    docs = await db.categories.find({"branch_id": branch_id}, {"_id": 0}).sort("sort_order", 1).to_list(1000)
    return docs

@api.post("/categories")
async def create_category(body: CategoryCreate, user: dict = Depends(require_role("admin", "manager"))):
    if user["role"] == "manager" and user.get("branch_id") != body.branch_id:
        raise HTTPException(403, "Not your branch")
    c = Category(**body.model_dump())
    await db.categories.insert_one(c.model_dump())
    return c

@api.delete("/categories/{category_id}")
async def delete_category(category_id: str, user: dict = Depends(require_role("admin", "manager"))):
    cat = await db.categories.find_one({"id": category_id}, {"_id": 0})
    if not cat:
        raise HTTPException(404, "Not found")
    if user["role"] == "manager" and user.get("branch_id") != cat["branch_id"]:
        raise HTTPException(403, "Not your branch")
    await db.categories.delete_one({"id": category_id})
    await db.menu_items.delete_many({"category_id": category_id})
    return {"ok": True}

# ---------- Menu Items ----------
@api.get("/menu-items")
async def list_menu_items(branch_id: str, user: dict = Depends(get_current_user)):
    docs = await db.menu_items.find({"branch_id": branch_id}, {"_id": 0}).to_list(2000)
    return docs

@api.post("/menu-items")
async def create_menu_item(body: MenuItemCreate, user: dict = Depends(require_role("admin", "manager"))):
    if user["role"] == "manager" and user.get("branch_id") != body.branch_id:
        raise HTTPException(403, "Not your branch")
    item = MenuItem(**body.model_dump())
    await db.menu_items.insert_one(item.model_dump())
    return item

@api.patch("/menu-items/{item_id}")
async def update_menu_item(item_id: str, body: MenuItemCreate, user: dict = Depends(require_role("admin", "manager"))):
    item = await db.menu_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Not found")
    if user["role"] == "manager" and user.get("branch_id") != item["branch_id"]:
        raise HTTPException(403, "Not your branch")
    await db.menu_items.update_one({"id": item_id}, {"$set": body.model_dump()})
    return await db.menu_items.find_one({"id": item_id}, {"_id": 0})

@api.delete("/menu-items/{item_id}")
async def delete_menu_item(item_id: str, user: dict = Depends(require_role("admin", "manager"))):
    item = await db.menu_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Not found")
    if user["role"] == "manager" and user.get("branch_id") != item["branch_id"]:
        raise HTTPException(403, "Not your branch")
    await db.menu_items.delete_one({"id": item_id})
    return {"ok": True}

# ---------- Bookings ----------
def _check_conflict_query(branch_id: str, event_date: str, start: str, end: str, exclude_id: Optional[str] = None):
    # Two intervals overlap iff existing.start < new.end AND new.start < existing.end
    q = {
        "branch_id": branch_id,
        "event_date": event_date,
        "status": {"$ne": "cancelled"},
        "event_time": {"$lt": end},
        "event_end_time": {"$gt": start},
    }
    if exclude_id:
        q["id"] = {"$ne": exclude_id}
    return q

@api.get("/bookings")
async def list_bookings(branch_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {}
    if user["role"] in ("user", "manager"):
        q["branch_id"] = user.get("branch_id")
    elif branch_id:
        q["branch_id"] = branch_id
    docs = await db.bookings.find(q, {"_id": 0}).to_list(5000)
    return docs

@api.post("/bookings")
async def create_booking(body: BookingCreate, user: dict = Depends(get_current_user)):
    # Branch enforcement for non-admin
    if user["role"] != "admin" and user.get("branch_id") != body.branch_id:
        raise HTTPException(403, "Not your branch")
    if not body.ignore_conflict:
        existing = await db.bookings.find_one(_check_conflict_query(body.branch_id, body.event_date, body.event_time, body.event_end_time))
        if existing:
            raise HTTPException(status_code=409, detail={"code": "TIME_CONFLICT", "existing_id": existing["id"]})
    branch = await db.branches.find_one({"id": body.branch_id}, {"_id": 0})
    gst = branch.get("gst_percent", 18.0) if branch else 18.0
    bk = Booking(
        **{k: v for k, v in body.model_dump().items() if k != "ignore_conflict"},
        gst_percent=gst,
        created_by=user["id"],
    )
    await db.bookings.insert_one(bk.model_dump())
    return bk

@api.patch("/bookings/{booking_id}")
async def update_booking(booking_id: str, body: BookingUpdate, user: dict = Depends(get_current_user)):
    bk = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not bk:
        raise HTTPException(404, "Not found")
    if user["role"] != "admin" and user.get("branch_id") != bk["branch_id"]:
        raise HTTPException(403, "Forbidden")
    update = {k: v for k, v in body.model_dump().items() if v is not None and k != "ignore_conflict"}
    # Conflict check if date/time changed
    new_date = update.get("event_date", bk["event_date"])
    new_start = update.get("event_time", bk["event_time"])
    new_end = update.get("event_end_time", bk.get("event_end_time", bk["event_time"]))
    time_changed = new_date != bk["event_date"] or new_start != bk["event_time"] or new_end != bk.get("event_end_time")
    if time_changed and not body.ignore_conflict:
        existing = await db.bookings.find_one(_check_conflict_query(bk["branch_id"], new_date, new_start, new_end, exclude_id=booking_id))
        if existing:
            raise HTTPException(status_code=409, detail={"code": "TIME_CONFLICT", "existing_id": existing["id"]})
    if update:
        await db.bookings.update_one({"id": booking_id}, {"$set": update})
    return await db.bookings.find_one({"id": booking_id}, {"_id": 0})

@api.delete("/bookings/{booking_id}")
async def delete_booking(booking_id: str, user: dict = Depends(get_current_user)):
    bk = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not bk:
        raise HTTPException(404, "Not found")
    if user["role"] != "admin" and user.get("branch_id") != bk["branch_id"]:
        raise HTTPException(403, "Forbidden")
    await db.bookings.delete_one({"id": booking_id})
    return {"ok": True}

# ---------- Settings ----------
@api.get("/settings")
async def get_settings():
    s = await db.settings.find_one({"id": "global"}, {"_id": 0})
    if not s:
        s = {"id": "global", "company_logo": ""}
        await db.settings.insert_one(s)
    return s

@api.patch("/settings")
async def update_settings(body: Settings, user: dict = Depends(require_role("admin"))):
    await db.settings.update_one({"id": "global"}, {"$set": body.model_dump()}, upsert=True)
    return await db.settings.find_one({"id": "global"}, {"_id": 0})

# ---------- Analytics ----------
@api.get("/analytics/summary")
async def analytics_summary(branch_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        branch_id = user.get("branch_id")
    q = {"status": {"$ne": "cancelled"}}
    if branch_id:
        q["branch_id"] = branch_id
    docs = await db.bookings.find(q, {"_id": 0}).to_list(10000)

    def total_for(bk: dict) -> float:
        subtotal = sum(it["price"] * it["quantity"] for it in bk["items"])
        disc = bk.get("discount_amount", 0) + subtotal * (bk.get("discount_percent", 0) / 100)
        taxable = max(0, subtotal - disc)
        gst = taxable * (bk.get("gst_percent", 18) / 100)
        return taxable + gst + bk.get("transportation_cost", 0)

    today = datetime.now(timezone.utc).date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    daily = {"bookings": 0, "sales": 0.0}
    weekly = {"bookings": 0, "sales": 0.0}
    monthly = {"bookings": 0, "sales": 0.0}
    yearly = {"bookings": 0, "sales": 0.0}

    daily_series = {}  # last 30 days
    monthly_series = {}  # last 12 months

    for bk in docs:
        try:
            d = datetime.strptime(bk["event_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        amt = total_for(bk)
        if d == today:
            daily["bookings"] += 1; daily["sales"] += amt
        if d >= week_start:
            weekly["bookings"] += 1; weekly["sales"] += amt
        if d >= month_start:
            monthly["bookings"] += 1; monthly["sales"] += amt
        if d >= year_start:
            yearly["bookings"] += 1; yearly["sales"] += amt
        if (today - d).days >= 0 and (today - d).days < 30:
            k = d.isoformat()
            daily_series.setdefault(k, {"date": k, "bookings": 0, "sales": 0.0})
            daily_series[k]["bookings"] += 1
            daily_series[k]["sales"] += amt
        if d.year == today.year or (today.year - d.year == 1 and d.month >= today.month):
            mk = d.strftime("%Y-%m")
            monthly_series.setdefault(mk, {"month": mk, "bookings": 0, "sales": 0.0})
            monthly_series[mk]["bookings"] += 1
            monthly_series[mk]["sales"] += amt

    return {
        "daily": daily, "weekly": weekly, "monthly": monthly, "yearly": yearly,
        "daily_series": sorted(daily_series.values(), key=lambda x: x["date"]),
        "monthly_series": sorted(monthly_series.values(), key=lambda x: x["month"]),
    }

# ---------- Seed ----------
async def seed():
    # Admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@udcatering.com").lower()
    admin_pw = os.environ.get("ADMIN_PASSWORD", "admin123")
    if not await db.users.find_one({"username": admin_email, "role": "admin"}):
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "username": admin_email,
            "password_hash": hash_pw(admin_pw),
            "role": "admin",
            "branch_id": None,
            "created_at": now_iso(),
        })

    # Branches
    if await db.branches.count_documents({}) == 0:
        branches_to_seed = [
            {"name": "UD Catering — Main Hall", "address": "12 MG Road, Bengaluru, KA", "gst_percent": 18.0},
            {"name": "UD Catering — Downtown", "address": "45 Brigade Road, Bengaluru, KA", "gst_percent": 18.0},
        ]
        for bdata in branches_to_seed:
            b = Branch(**bdata)
            await db.branches.insert_one(b.model_dump())
        # Manager + user per branch + menu
        branches = await db.branches.find({}, {"_id": 0}).to_list(10)
        sample_menu = {
            "Appetizers": [("Paneer Tikka", 280), ("Veg Manchurian", 220), ("Chicken 65", 320), ("Hara Bhara Kebab", 240)],
            "Main Course": [("Butter Chicken", 380), ("Paneer Butter Masala", 320), ("Dal Makhani", 260), ("Veg Biryani", 280)],
            "Breads": [("Butter Naan", 50), ("Tandoori Roti", 30), ("Lachha Paratha", 60)],
            "Rice & Pulao": [("Jeera Rice", 180), ("Hyderabadi Biryani", 350)],
            "Desserts": [("Gulab Jamun", 80), ("Rasmalai", 120), ("Gajar Halwa", 140)],
            "Beverages": [("Masala Chai", 40), ("Sweet Lassi", 80), ("Fresh Lime Soda", 60)],
        }
        for i, br in enumerate(branches, start=1):
            # Manager
            mu = f"manager{i}"
            if not await db.users.find_one({"username": mu, "role": "manager"}):
                await db.users.insert_one({
                    "id": str(uuid.uuid4()), "username": mu,
                    "password_hash": hash_pw("manager123"),
                    "role": "manager", "branch_id": br["id"], "created_at": now_iso(),
                })
            uu = f"staff{i}"
            if not await db.users.find_one({"username": uu, "role": "user"}):
                await db.users.insert_one({
                    "id": str(uuid.uuid4()), "username": uu,
                    "password_hash": hash_pw("staff123"),
                    "role": "user", "branch_id": br["id"], "created_at": now_iso(),
                })
            # Menu
            for sort_idx, (cat_name, items) in enumerate(sample_menu.items()):
                c = Category(branch_id=br["id"], name=cat_name, sort_order=sort_idx)
                await db.categories.insert_one(c.model_dump())
                for name, price in items:
                    mi = MenuItem(branch_id=br["id"], category_id=c.id, name=name, price=price)
                    await db.menu_items.insert_one(mi.model_dump())

    if not await db.settings.find_one({"id": "global"}):
        await db.settings.insert_one({"id": "global", "company_logo": ""})

@app.on_event("startup")
async def on_start():
    await db.users.create_index([("username", 1), ("role", 1)], unique=True)
    # Backfill: any existing booking without event_end_time gets start + 3h
    cursor = db.bookings.find({"event_end_time": {"$exists": False}}, {"_id": 0, "id": 1, "event_time": 1})
    async for bk in cursor:
        try:
            h, m = [int(x) for x in bk["event_time"].split(":")]
            end_h = (h + 3) % 24
            end = f"{end_h:02d}:{m:02d}"
        except Exception:
            end = "23:59"
        await db.bookings.update_one({"id": bk["id"]}, {"$set": {"event_end_time": end}})
    await seed()

@app.on_event("shutdown")
async def on_stop():
    client.close()

app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
