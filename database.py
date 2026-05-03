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
 
 
# ══════════════════════════════════════════
# РЕГИСТРАЦИЯ ПАРТНЁРОВ
# ══════════════════════════════════════════
 
async def create_venue_application(data: dict) -> dict | None:
    """Создать заявку на регистрацию заведения."""
    try:
        res = supabase.table("venue_applications").insert({
            **data,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "status": "pending",
        }).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        return None
 
async def update_venue_application(app_id: int, data: dict) -> bool:
    """Обновить заявку."""
    try:
        data["updated_at"] = datetime.utcnow().isoformat()
        supabase.table("venue_applications").update(data).eq("id", app_id).execute()
        return True
    except Exception:
        return False
 
async def get_venue_application(app_id: int) -> dict | None:
    try:
        return supabase.table("venue_applications").select("*").eq("id", app_id).single().execute().data
    except Exception:
        return None
 
async def get_application_by_tg(tg_id: int) -> dict | None:
    """Получить активную заявку пользователя."""
    try:
        res = supabase.table("venue_applications").select("*") \
            .eq("admin_telegram_id", tg_id) \
            .in_("status", ["pending", "payment_pending"]) \
            .order("created_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None
 
async def approve_venue_application(app_id: int) -> dict | None:
    """Одобрить заявку и создать заведение."""
    try:
        app = await get_venue_application(app_id)
        if not app:
            return None
 
        # Создаём заведение
        TYPE_EMOJI = {
            "restaurant": "🍽️", "cafe": "☕",
            "hookah": "💨", "karaoke": "🎤",
            "billiard": "🎱", "bar": "🍺",
        }
        TYPE_LABEL = {
            "restaurant": "Ресторан", "cafe": "Кафе",
            "hookah": "Кальянная", "karaoke": "Каракое",
            "billiard": "Бильярдная", "bar": "Бар",
        }
 
        venue_data = {
            "name":              app["brand_name"],
            "type":              app["venue_type"],
            "type_label":        TYPE_LABEL.get(app["venue_type"], ""),
            "emoji":             TYPE_EMOJI.get(app["venue_type"], "🍽️"),
            "address":           app["actual_address"] or app["legal_address"],
            "description":       app.get("description", ""),
            "avg_check":         app.get("avg_check", ""),
            "video_url":         app.get("video_url"),
            "photos":            app.get("photos", []),
            "admin_telegram_id": app["admin_telegram_id"],
            "subscription_plan": app["plan"],
            "is_active":         True,
            "is_available":      True,
            "promo_applied":     app.get("promo_applied", False),
            "referral_code":     app.get("referral_code"),
            "created_at":        datetime.utcnow().isoformat(),
        }
 
        venue_res = supabase.table("venues").insert(venue_data).execute()
        venue = venue_res.data[0] if venue_res.data else None
 
        # Обновляем статус заявки
        await update_venue_application(app_id, {"status": "approved"})
 
        # Обновляем реферала если есть
        if app.get("referral_code"):
            await increment_referral(app["referral_code"])
 
        return venue
    except Exception as e:
        return None
 
async def reject_venue_application(app_id: int, reason: str) -> bool:
    """Отклонить заявку."""
    return await update_venue_application(app_id, {
        "status": "rejected",
        "reject_reason": reason,
    })
 
 
# ══════════════════════════════════════════
# ПРОМО-СЧЁТЧИК
# ══════════════════════════════════════════
 
async def get_promo_counter() -> dict:
    """Получить состояние промо-счётчика."""
    try:
        res = supabase.table("promo_counter").select("*").eq("id", 1).single().execute()
        return res.data or {"total_slots": 50, "used_slots": 0, "is_active": True}
    except Exception:
        return {"total_slots": 50, "used_slots": 0, "is_active": True}
 
async def get_promo_slots_left() -> int:
    """Сколько акционных мест осталось."""
    counter = await get_promo_counter()
    if not counter["is_active"]:
        return 0
    return max(0, counter["total_slots"] - counter["used_slots"])
 
async def use_promo_slot() -> bool:
    """Занять одно акционное место. Возвращает True если успешно."""
    try:
        counter = await get_promo_counter()
        if not counter["is_active"]:
            return False
        left = counter["total_slots"] - counter["used_slots"]
        if left <= 0:
            return False
        supabase.table("promo_counter").update({
            "used_slots": counter["used_slots"] + 1,
            "is_active": (left - 1) > 0
        }).eq("id", 1).execute()
        return True
    except Exception:
        return False
 
 
# ══════════════════════════════════════════
# РЕФЕРАЛЬНАЯ ПРОГРАММА
# ══════════════════════════════════════════
 
async def get_or_create_referral_code(tg_id: int) -> str:
    """Получить или создать реферальный код партнёра."""
    try:
        res = supabase.table("referrals").select("code").eq("referrer_tg_id", tg_id).single().execute()
        return res.data["code"]
    except Exception:
        pass
    # Создаём новый код
    import hashlib
    code = hashlib.md5(f"reserva_{tg_id}".encode()).hexdigest()[:8].upper()
    try:
        supabase.table("referrals").insert({
            "referrer_tg_id": tg_id,
            "code": code,
            "referrals_count": 0,
            "bonus_months": 0,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass
    return code
 
async def get_referral_by_code(code: str) -> dict | None:
    try:
        return supabase.table("referrals").select("*").eq("code", code.upper()).single().execute().data
    except Exception:
        return None
 
async def increment_referral(code: str) -> bool:
    """Увеличить счётчик рефералов и начислить бонус."""
    try:
        ref = await get_referral_by_code(code)
        if not ref:
            return False
        new_count = ref["referrals_count"] + 1
        # Бонусные месяцы: 1 реферал=1мес, 3=3мес, 5=6мес
        bonus = 1
        if new_count >= 5:
            bonus = 6
        elif new_count >= 3:
            bonus = 3
        supabase.table("referrals").update({
            "referrals_count": new_count,
            "bonus_months": ref["bonus_months"] + bonus,
        }).eq("code", code.upper()).execute()
        return True
    except Exception:
        return False
 
async def get_referral_stats(tg_id: int) -> dict:
    """Статистика рефералов партнёра."""
    try:
        res = supabase.table("referrals").select("*").eq("referrer_tg_id", tg_id).single().execute()
        return res.data or {"referrals_count": 0, "bonus_months": 0}
    except Exception:
        return {"referrals_count": 0, "bonus_months": 0}
