"""
menu.py — функции базы данных для модуля меню.
Подключается к существующему supabase из database.py.
"""
from database import supabase
from datetime import datetime


# ══════════════════════════════════════════
# КАТЕГОРИИ МЕНЮ
# ══════════════════════════════════════════

async def get_menu_categories(venue_id: int) -> list:
    """Получить все категории меню заведения, отсортированные по sort_order."""
    try:
        res = supabase.table("menu_categories") \
            .select("*") \
            .eq("venue_id", venue_id) \
            .order("sort_order") \
            .execute()
        return res.data or []
    except Exception:
        return []


async def create_menu_category(venue_id: int, name: str) -> dict | None:
    """Создать новую категорию меню."""
    try:
        # Определяем следующий sort_order
        existing = await get_menu_categories(venue_id)
        sort_order = len(existing)

        res = supabase.table("menu_categories").insert({
            "venue_id":   venue_id,
            "name":       name.strip(),
            "sort_order": sort_order,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


async def update_menu_category(category_id: int, data: dict) -> bool:
    """Обновить категорию (название или порядок)."""
    try:
        supabase.table("menu_categories") \
            .update(data) \
            .eq("id", category_id) \
            .execute()
        return True
    except Exception:
        return False


async def delete_menu_category(category_id: int) -> bool:
    """Удалить категорию и все её блюда."""
    try:
        # Блюда удалятся каскадно (ON DELETE CASCADE в схеме)
        supabase.table("menu_categories").delete().eq("id", category_id).execute()
        return True
    except Exception:
        return False


# ══════════════════════════════════════════
# БЛЮДА
# ══════════════════════════════════════════

async def get_menu_items(venue_id: int, category_id: int = None) -> list:
    """Получить блюда. Если category_id не указан — все блюда заведения."""
    try:
        q = supabase.table("menu_items") \
            .select("*, menu_categories(name)") \
            .eq("venue_id", venue_id) \
            .order("sort_order")
        if category_id:
            q = q.eq("category_id", category_id)
        return q.execute().data or []
    except Exception:
        return []


async def get_menu_item(item_id: int) -> dict | None:
    """Получить одно блюдо по ID."""
    try:
        res = supabase.table("menu_items") \
            .select("*") \
            .eq("id", item_id) \
            .single() \
            .execute()
        return res.data
    except Exception:
        return None


async def create_menu_item(data: dict) -> dict | None:
    """
    Создать блюдо.
    data: venue_id, category_id, name, price, description,
          media_url, media_type, is_hit, is_new, is_available
    """
    try:
        existing = await get_menu_items(data["venue_id"], data.get("category_id"))
        res = supabase.table("menu_items").insert({
            "venue_id":    data["venue_id"],
            "category_id": data["category_id"],
            "name":        data["name"].strip(),
            "price":       int(data["price"]),
            "description": data.get("description", "").strip(),
            "media_url":   data.get("media_url"),
            "media_type":  data.get("media_type", "jpg"),  # jpg | png | gif
            "is_hit":      data.get("is_hit", False),
            "is_new":      data.get("is_new", False),
            "is_available": data.get("is_available", True),
            "sort_order":  len(existing),
            "created_at":  datetime.utcnow().isoformat(),
        }).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


async def update_menu_item(item_id: int, data: dict) -> bool:
    """Обновить поля блюда."""
    try:
        data["updated_at"] = datetime.utcnow().isoformat()
        supabase.table("menu_items").update(data).eq("id", item_id).execute()
        return True
    except Exception:
        return False


async def delete_menu_item(item_id: int) -> bool:
    """Удалить блюдо."""
    try:
        supabase.table("menu_items").delete().eq("id", item_id).execute()
        return True
    except Exception:
        return False


async def toggle_item_availability(item_id: int) -> bool | None:
    """
    Переключить доступность блюда.
    Возвращает новое значение is_available или None при ошибке.
    """
    try:
        item = await get_menu_item(item_id)
        if not item:
            return None
        new_val = not item["is_available"]
        await update_menu_item(item_id, {"is_available": new_val})
        return new_val
    except Exception:
        return None


# ══════════════════════════════════════════
# ПОЛНОЕ МЕНЮ (для мини-апп и предзаказа)
# ══════════════════════════════════════════

async def get_full_menu(venue_id: int) -> list:
    """
    Возвращает меню в виде:
    [
      {
        "id": 1,
        "name": "Горячее",
        "sort_order": 0,
        "items": [ { блюдо }, ... ]
      },
      ...
    ]
    Только доступные блюда (is_available=True).
    """
    try:
        categories = await get_menu_categories(venue_id)
        result = []
        for cat in categories:
            items_res = supabase.table("menu_items") \
                .select("*") \
                .eq("venue_id", venue_id) \
                .eq("category_id", cat["id"]) \
                .eq("is_available", True) \
                .order("sort_order") \
                .execute()
            result.append({
                **cat,
                "items": items_res.data or []
            })
        return result
    except Exception:
        return []


# ══════════════════════════════════════════
# ПРЕДЗАКАЗ
# ══════════════════════════════════════════

async def save_preorder(booking_id: int, items: list) -> bool:
    """
    Сохранить предзаказ к бронированию.
    items: [{"item_id": int, "quantity": int, "price": int, "name": str}, ...]
    """
    try:
        rows = [{
            "booking_id": booking_id,
            "item_id":    it["item_id"],
            "name":       it["name"],
            "quantity":   it["quantity"],
            "price":      it["price"],
            "total":      it["price"] * it["quantity"],
            "created_at": datetime.utcnow().isoformat(),
        } for it in items]
        supabase.table("preorder_items").insert(rows).execute()
        return True
    except Exception:
        return False


async def get_preorder(booking_id: int) -> list:
    """Получить предзаказ по ID брони."""
    try:
        res = supabase.table("preorder_items") \
            .select("*") \
            .eq("booking_id", booking_id) \
            .execute()
        return res.data or []
    except Exception:
        return []


async def format_preorder_text(booking_id: int) -> str:
    """Форматировать предзаказ для уведомления."""
    items = await get_preorder(booking_id)
    if not items:
        return ""
    lines = ["\n🍽 Предзаказ:"]
    total = 0
    for it in items:
        lines.append(f"  • {it['name']} × {it['quantity']} = {it['total']:,} ₸".replace(",", " "))
        total += it["total"]
    lines.append(f"  Итого: {total:,} ₸".replace(",", " "))
    return "\n".join(lines)
