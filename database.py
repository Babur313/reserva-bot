from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY
from datetime import datetime

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── ПОЛЬЗОВАТЕЛИ ──

async def upsert_user(tg_id: int, data: dict):
    return supabase.table("users").upsert(
        {"telegram_id": tg_id, "updated_at": datetime.utcnow().isoformat(), **data},
        on_conflict="telegram_id"
    ).execute()

async def get_user(tg_id: int):
    try:
        res = supabase.table("users").select("*").eq("telegram_id", tg_id).single().execute()
        return res.data
    except Exception:
        return None

async def set_consent(tg_id: int, consent: bool):
    supabase.table("users").update({
        "marketing_consent": consent,
        "consent_at": datetime.utcnow().isoformat()
    }).eq("telegram_id", tg_id).execute()

async def set_user_lang(tg_id: int, lang: str):
    """Сохранить язык пользователя: ru | kz | en"""
    supabase.table("users").update({
        "lang": lang,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("telegram_id", tg_id).execute()

async def set_user_city(tg_id: int, city: str):
    """Сохранить город пользователя."""
    supabase.table("users").update({
        "city": city,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("telegram_id", tg_id).execute()

# ── ЗАВЕДЕНИЯ ──

async def get_venues(type_filter: str = None, available_only: bool = False):
    q = supabase.table("venues").select("*").eq("is_active", True)
    if type_filter and type_filter != "all":
        q = q.eq("type", type_filter)
    if available_only:
        q = q.eq("is_available", True)
    return q.execute().data or []

async def get_venue(venue_id: int):
    try:
        return supabase.table("venues").select("*").eq("id", venue_id).single().execute().data
    except Exception:
        return None

async def get_venue_admin(tg_id: int):
    try:
        return supabase.table("venues").select("*").eq("admin_telegram_id", tg_id).single().execute().data
    except Exception:
        return None

async def update_venue(venue_id: int, data: dict):
    return supabase.table("venues").update(data).eq("id", venue_id).execute()

# ── БРОНИРОВАНИЯ ──

async def create_booking(data: dict):
    return supabase.table("bookings").insert({
        **data,
        "created_at": datetime.utcnow().isoformat(),
        "status": "pending"
    }).execute()

async def get_user_bookings(tg_id: int):
    return supabase.table("bookings").select(
        "*, venues(name, address, emoji)"
    ).eq("user_telegram_id", tg_id).order("created_at", desc=True).limit(10).execute().data or []

async def update_booking_status(booking_id: int, status: str):
    return supabase.table("bookings").update({
        "status": status,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", booking_id).execute()

async def get_venue_bookings(venue_id: int, pending_only: bool = True):
    q = supabase.table("bookings").select(
        "*, users(first_name, phone)"
    ).eq("venue_id", venue_id).order("booking_date")
    if pending_only:
        q = q.eq("status", "pending")
    return q.execute().data or []
