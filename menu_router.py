"""
menu_router.py — FastAPI роутер для модуля меню.
Подключается в main.py одной строкой.

Эндпоинты:
  GET    /menu/{venue_id}                     — полное меню (публичное, для мини-апп)
  GET    /menu/{venue_id}/admin               — меню с неактивными блюдами (для партнёра)
  POST   /menu/{venue_id}/categories          — создать категорию
  PATCH  /menu/categories/{category_id}       — переименовать категорию
  DELETE /menu/categories/{category_id}       — удалить категорию
  POST   /menu/{venue_id}/items               — создать блюдо
  PATCH  /menu/items/{item_id}               — обновить поля блюда
  DELETE /menu/items/{item_id}               — удалить блюдо
  POST   /menu/items/{item_id}/toggle        — вкл/выкл доступность
  POST   /menu/upload                        — загрузить фото/GIF в Supabase Storage
  POST   /menu/preorder/{booking_id}         — сохранить предзаказ
  GET    /menu/preorder/{booking_id}         — получить предзаказ
"""

import logging
import uuid
import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from menu import (
    get_menu_categories, create_menu_category,
    update_menu_category, delete_menu_category,
    get_menu_items, get_menu_item,
    create_menu_item, update_menu_item,
    delete_menu_item, toggle_item_availability,
    get_full_menu, save_preorder, get_preorder
)
from database import supabase
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)
menu_router = APIRouter(prefix="/menu", tags=["menu"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 МБ


# ══════════════════════════════════════════
# PYDANTIC СХЕМЫ
# ══════════════════════════════════════════

class CategoryCreate(BaseModel):
    name: str

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    sort_order: Optional[int] = None

class ItemCreate(BaseModel):
    category_id: int
    name: str
    price: int
    description: Optional[str] = ""
    media_url: Optional[str] = None
    media_type: Optional[str] = "jpg"
    is_hit: Optional[bool] = False
    is_new: Optional[bool] = False

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    is_hit: Optional[bool] = None
    is_new: Optional[bool] = None
    is_available: Optional[bool] = None
    category_id: Optional[int] = None

class PreorderItem(BaseModel):
    item_id: int
    name: str
    quantity: int
    price: int

class PreorderCreate(BaseModel):
    items: list[PreorderItem]


# ══════════════════════════════════════════
# МЕНЮ — ПУБЛИЧНОЕ (для мини-апп)
# ══════════════════════════════════════════

@menu_router.get("/{venue_id}")
async def get_venue_menu(venue_id: int):
    """Полное меню заведения — только доступные блюда."""
    menu = await get_full_menu(venue_id)
    return {"venue_id": venue_id, "menu": menu}


@menu_router.get("/{venue_id}/admin")
async def get_venue_menu_admin(venue_id: int):
    """Меню для партнёра — все блюда включая недоступные."""
    categories = await get_menu_categories(venue_id)
    result = []
    for cat in categories:
        items = await get_menu_items(venue_id, cat["id"])
        result.append({**cat, "items": items})
    return {"venue_id": venue_id, "menu": result}


# ══════════════════════════════════════════
# КАТЕГОРИИ
# ══════════════════════════════════════════

@menu_router.post("/{venue_id}/categories")
async def add_category(venue_id: int, body: CategoryCreate):
    if not body.name.strip():
        raise HTTPException(400, "Название категории не может быть пустым")
    cat = await create_menu_category(venue_id, body.name)
    if not cat:
        raise HTTPException(500, "Ошибка создания категории")
    return cat

@menu_router.patch("/categories/{category_id}")
async def edit_category(category_id: int, body: CategoryUpdate):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(400, "Нет данных для обновления")
    ok = await update_menu_category(category_id, data)
    if not ok:
        raise HTTPException(500, "Ошибка обновления категории")
    return {"ok": True}

@menu_router.delete("/categories/{category_id}")
async def remove_category(category_id: int):
    ok = await delete_menu_category(category_id)
    if not ok:
        raise HTTPException(500, "Ошибка удаления категории")
    return {"ok": True}


# ══════════════════════════════════════════
# БЛЮДА
# ══════════════════════════════════════════

@menu_router.post("/{venue_id}/items")
async def add_item(venue_id: int, body: ItemCreate):
    if not body.name.strip():
        raise HTTPException(400, "Название блюда не может быть пустым")
    if body.price <= 0:
        raise HTTPException(400, "Цена должна быть больше нуля")

    item = await create_menu_item({
        "venue_id":    venue_id,
        "category_id": body.category_id,
        "name":        body.name,
        "price":       body.price,
        "description": body.description or "",
        "media_url":   body.media_url,
        "media_type":  body.media_type or "jpg",
        "is_hit":      body.is_hit,
        "is_new":      body.is_new,
    })
    if not item:
        raise HTTPException(500, "Ошибка создания блюда")
    return item

@menu_router.patch("/items/{item_id}")
async def edit_item(item_id: int, body: ItemUpdate):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(400, "Нет данных для обновления")
    ok = await update_menu_item(item_id, data)
    if not ok:
        raise HTTPException(500, "Ошибка обновления блюда")
    return {"ok": True}

@menu_router.delete("/items/{item_id}")
async def remove_item(item_id: int):
    ok = await delete_menu_item(item_id)
    if not ok:
        raise HTTPException(500, "Ошибка удаления блюда")
    return {"ok": True}

@menu_router.post("/items/{item_id}/toggle")
async def toggle_item(item_id: int):
    """Вкл/выкл доступность блюда."""
    new_val = await toggle_item_availability(item_id)
    if new_val is None:
        raise HTTPException(500, "Ошибка переключения доступности")
    return {"ok": True, "is_available": new_val}


# ══════════════════════════════════════════
# ЗАГРУЗКА ФАЙЛОВ (фото и GIF)
# ══════════════════════════════════════════

@menu_router.post("/upload")
async def upload_media(
    venue_id: int = Form(...),
    file: UploadFile = File(...)
):
    """
    Загружает JPG / PNG / GIF / WEBP в Supabase Storage.
    Возвращает публичный URL и тип медиа (jpg / gif).
    Лимит: 10 МБ.
    """
    # Проверка типа
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            400,
            f"Недопустимый тип файла: {file.content_type}. "
            f"Разрешены: JPG, PNG, GIF, WEBP"
        )

    # Читаем файл
    content = await file.read()

    # Проверка размера
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            400,
            f"Файл слишком большой ({len(content)//1024//1024} МБ). Максимум 10 МБ"
        )

    # Определяем расширение и media_type
    ext_map = {
        "image/jpeg": ("jpg", "jpg"),
        "image/png":  ("png", "jpg"),
        "image/gif":  ("gif", "gif"),
        "image/webp": ("webp", "jpg"),
    }
    ext, media_type = ext_map[file.content_type]

    # Генерируем уникальное имя файла
    filename = f"venues/{venue_id}/menu/{uuid.uuid4().hex}.{ext}"

    # Загружаем в Supabase Storage через REST API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/menu-media/{filename}",
                headers={
                    "apikey":        SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type":  file.content_type,
                    "x-upsert":      "false",
                },
                content=content,
                timeout=30.0
            )

        if response.status_code not in (200, 201):
            logger.error(f"Supabase Storage error: {response.text}")
            raise HTTPException(500, "Ошибка загрузки файла в хранилище")

        # Публичный URL
        public_url = (
            f"{SUPABASE_URL}/storage/v1/object/public/menu-media/{filename}"
        )

        return {
            "url":        public_url,
            "media_type": media_type,  # "gif" или "jpg"
            "filename":   filename,
            "size_kb":    round(len(content) / 1024),
        }

    except httpx.TimeoutException:
        raise HTTPException(504, "Таймаут при загрузке файла")
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(500, "Внутренняя ошибка при загрузке")


# ══════════════════════════════════════════
# ПРЕДЗАКАЗ
# ══════════════════════════════════════════

@menu_router.post("/preorder/{booking_id}")
async def create_preorder(booking_id: int, body: PreorderCreate):
    """Сохранить предзаказ к бронированию."""
    if not body.items:
        raise HTTPException(400, "Список блюд пустой")

    items_data = [
        {
            "item_id":  it.item_id,
            "name":     it.name,
            "quantity": it.quantity,
            "price":    it.price,
        }
        for it in body.items
    ]
    ok = await save_preorder(booking_id, items_data)
    if not ok:
        raise HTTPException(500, "Ошибка сохранения предзаказа")

    total = sum(it.price * it.quantity for it in body.items)
    return {"ok": True, "booking_id": booking_id, "total": total}


@menu_router.get("/preorder/{booking_id}")
async def fetch_preorder(booking_id: int):
    """Получить предзаказ."""
    items = await get_preorder(booking_id)
    total = sum(it["total"] for it in items)
    return {"booking_id": booking_id, "items": items, "total": total}
