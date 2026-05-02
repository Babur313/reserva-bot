import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import ADMIN_BOT_TOKEN
from database import (
    get_venue_admin, update_venue,
    get_venue_bookings, update_booking_status, get_venue,
    set_user_lang, upsert_user, get_user
)
from menu import (
    get_menu_categories, create_menu_category, delete_menu_category,
    get_menu_items, get_menu_item, create_menu_item,
    update_menu_item, delete_menu_item, toggle_item_availability
)

logger = logging.getLogger(__name__)

admin_bot = Bot(token=ADMIN_BOT_TOKEN)
admin_storage = MemoryStorage()
admin_dp = Dispatcher(storage=admin_storage)
admin_router = Router()
admin_dp.include_router(admin_router)


class AdminState(StatesGroup):
    edit_description    = State()
    edit_avg_check      = State()
    edit_video_url      = State()
    add_menu_item       = State()
    menu_add_cat_name   = State()
    menu_add_dish_cat   = State()
    menu_add_dish_name  = State()
    menu_add_dish_price = State()
    menu_add_dish_desc  = State()
    pick_lang           = State()


# Языки для партнёрского бота
ADMIN_LANGS = {
    "🇷🇺 Русский":  "ru",
    "🇰🇿 Қазақша": "kz",
    "🇬🇧 English":  "en",
}

# Строки интерфейса партнёрского бота
ADMIN_T = {
    "ru": {
        "choose_lang":   "Выберите язык кабинета:",
        "lang_saved":    "Язык сохранён ✅",
        "not_connected": (
            "Добро пожаловать в кабинет партнёра Reserva!\n\n"
            "Ваш аккаунт ещё не подключён к заведению.\n\n"
            "Для подключения напишите: @reserva_support\n"
            "Укажите:\n• Название заведения\n• Адрес\n• Ваш контакт\n\n"
            "Тарифы:\n• Старт — 4 900 ₸/мес\n• Бизнес — 7 900 ₸/мес\n• Про — 9 900 ₸/мес\n\n"
            "Подключение в течение 24 часов."
        ),
    },
    "kz": {
        "choose_lang":   "Кабинет тілін таңдаңыз:",
        "lang_saved":    "Тіл сақталды ✅",
        "not_connected": (
            "Reserva серіктес кабинетіне қош келдіңіз!\n\n"
            "Сіздің аккаунтыңыз мекемеге әлі қосылмаған.\n\n"
            "Қосылу үшін жазыңыз: @reserva_support\n"
            "Көрсетіңіз:\n• Мекеме атауы\n• Мекенжайы\n• Байланысыңыз\n\n"
            "Тарифтер:\n• Старт — 4 900 ₸/ай\n• Бизнес — 7 900 ₸/ай\n• Про — 9 900 ₸/ай\n\n"
            "Қосылу 24 сағат ішінде."
        ),
    },
    "en": {
        "choose_lang":   "Choose cabinet language:",
        "lang_saved":    "Language saved ✅",
        "not_connected": (
            "Welcome to Reserva Partner Cabinet!\n\n"
            "Your account is not yet connected to a venue.\n\n"
            "To connect, write to: @reserva_support\n"
            "Include:\n• Venue name\n• Address\n• Your contact\n\n"
            "Plans:\n• Start — 4,900 ₸/mo\n• Business — 7,900 ₸/mo\n• Pro — 9,900 ₸/mo\n\n"
            "Connection within 24 hours."
        ),
    },
}

def admin_t(lang: str, key: str) -> str:
    return ADMIN_T.get(lang, ADMIN_T["ru"]).get(key, key)

def kb_admin_lang():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=lbl)] for lbl in ADMIN_LANGS],
        resize_keyboard=True, one_time_keyboard=True
    )


def kb_admin_main(is_available: bool = True):
    status = "⏸️ Остановить приём" if is_available else "▶️ Включить приём"
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔔 Новые брони")],
        [KeyboardButton(text="🍽️ Меню заведения")],
        [KeyboardButton(text="✏️ Профиль заведения")],
        [KeyboardButton(text=status)],
        [KeyboardButton(text="📊 Статистика")]
    ], resize_keyboard=True)

def kb_booking_actions(booking_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{booking_id}"),
        InlineKeyboardButton(text="❌ Отклонить",   callback_data=f"decline_{booking_id}")
    ]])

def kb_edit_profile():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Описание")],
        [KeyboardButton(text="💰 Средний чек")],
        [KeyboardButton(text="🎬 Ссылка на видео")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True)


# ── /start ──
@admin_router.message(CommandStart())
async def admin_start(msg: Message, state: FSMContext):
    await state.clear()

    # Регистрируем/получаем пользователя
    user = await get_user(msg.from_user.id)
    if not user:
        await upsert_user(msg.from_user.id, {
            "first_name": msg.from_user.first_name or "",
            "username":   msg.from_user.username or "",
            "lang":       None,
        })

    # Если язык не выбран — сначала выбор языка
    if not user or not user.get("lang"):
        await msg.answer(
            "Привет! · Сәлем! · Hello!\n\nВыберите язык · Тілді таңдаңыз · Choose language:",
            reply_markup=kb_admin_lang()
        )
        await state.set_state(AdminState.pick_lang)
        return

    await _show_admin_main(msg, user.get("lang", "ru"))


@admin_router.message(AdminState.pick_lang)
async def admin_pick_lang(msg: Message, state: FSMContext):
    lang_code = ADMIN_LANGS.get(msg.text)
    if not lang_code:
        await msg.answer(
            "Выберите из списка · Тізімнен таңдаңыз · Choose from the list:",
            reply_markup=kb_admin_lang()
        )
        return
    await set_user_lang(msg.from_user.id, lang_code)
    await state.clear()
    await msg.answer(admin_t(lang_code, "lang_saved"))
    await _show_admin_main(msg, lang_code)


async def _show_admin_main(msg: Message, lang: str):
    """Показать главный экран кабинета партнёра."""
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        await msg.answer(admin_t(lang, "not_connected"))
        return
    status = "✅ Приём броней включён" if venue["is_available"] else "⏸️ Приём броней остановлен"
    await msg.answer(
        f"{venue.get('emoji','')} {venue['name']}\n"
        f"📍 {venue.get('address','')}\n"
        f"💰 {venue.get('avg_check','')}\n"
        f"{status}",
        reply_markup=kb_admin_main(venue["is_available"])
    )


# ── Новые брони ──
@admin_router.message(F.text == "🔔 Новые брони")
async def admin_new_bookings(msg: Message):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return

    bookings = await get_venue_bookings(venue["id"], pending_only=True)
    if not bookings:
        await msg.answer("Новых броней нет ✨", reply_markup=kb_admin_main(venue["is_available"]))
        return

    await msg.answer(f"Новых броней: {len(bookings)}")
    for b in bookings:
        u = b.get("users") or {}
        text = (
            f"Бронь #{b['id']}\n\n"
            f"Гость: {u.get('first_name', 'Гость')}\n"
            f"Телефон: {b.get('phone') or '—'}\n"
            f"Дата: {b.get('booking_date')}, {b.get('booking_time')}\n"
            f"Гостей: {b.get('guests_count')}\n"
            f"Зона: {b.get('zone') or '—'}\n"
            f"Пожелания: {b.get('wishes') or '—'}"
        )
        await msg.answer(text, reply_markup=kb_booking_actions(b["id"]))


# ── Подтвердить бронь ──
@admin_router.callback_query(F.data.startswith("confirm_"))
async def cb_confirm(cb: CallbackQuery):
    booking_id = int(cb.data.split("_")[1])
    await update_booking_status(booking_id, "confirmed")
    await cb.message.edit_text(cb.message.text + "\n\n✅ ПОДТВЕРЖДЕНО")
    await notify_user_confirmed(booking_id)
    await cb.answer("Бронь подтверждена!")


# ── Отклонить бронь ──
@admin_router.callback_query(F.data.startswith("decline_"))
async def cb_decline(cb: CallbackQuery):
    booking_id = int(cb.data.split("_")[1])
    await update_booking_status(booking_id, "cancelled")
    await cb.message.edit_text(cb.message.text + "\n\n❌ ОТКЛОНЕНО")
    await notify_user_cancelled(booking_id)
    await cb.answer("Бронь отклонена")


# ── Вкл/Выкл приём броней ──
@admin_router.message(F.text.in_({"⏸️ Остановить приём", "▶️ Включить приём"}))
async def toggle_bookings(msg: Message):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return
    new_val = not venue["is_available"]
    await update_venue(venue["id"], {"is_available": new_val})
    status = "включён ✅" if new_val else "остановлен ⏸️"
    await msg.answer(f"Приём броней {status}", reply_markup=kb_admin_main(new_val))


# ── Редактировать профиль ──
@admin_router.message(F.text == "✏️ Профиль заведения")
async def edit_profile(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Что хотите изменить?", reply_markup=kb_edit_profile())


@admin_router.message(F.text == "📝 Описание")
async def ask_description(msg: Message, state: FSMContext):
    await msg.answer("Введите новое описание заведения (до 500 символов):")
    await state.set_state(AdminState.edit_description)

@admin_router.message(AdminState.edit_description)
async def save_description(msg: Message, state: FSMContext):
    venue = await get_venue_admin(msg.from_user.id)
    if venue:
        await update_venue(venue["id"], {"description": msg.text[:500]})
    await msg.answer("Описание обновлено ✅", reply_markup=kb_admin_main(venue["is_available"] if venue else True))
    await state.clear()


@admin_router.message(F.text == "💰 Средний чек")
async def ask_avg_check(msg: Message, state: FSMContext):
    await msg.answer("Введите средний чек, например: 5 000–9 000 ₸")
    await state.set_state(AdminState.edit_avg_check)

@admin_router.message(AdminState.edit_avg_check)
async def save_avg_check(msg: Message, state: FSMContext):
    venue = await get_venue_admin(msg.from_user.id)
    if venue:
        await update_venue(venue["id"], {"avg_check": msg.text})
    await msg.answer("Средний чек обновлён ✅", reply_markup=kb_admin_main(venue["is_available"] if venue else True))
    await state.clear()


@admin_router.message(F.text == "🎬 Ссылка на видео")
async def ask_video(msg: Message, state: FSMContext):
    await msg.answer("Введите ссылку на видео (YouTube, TikTok, Instagram Reels и т.д.):")
    await state.set_state(AdminState.edit_video_url)

@admin_router.message(AdminState.edit_video_url)
async def save_video(msg: Message, state: FSMContext):
    venue = await get_venue_admin(msg.from_user.id)
    if venue:
        await update_venue(venue["id"], {"video_url": msg.text})
    await msg.answer("Ссылка на видео обновлена ✅", reply_markup=kb_admin_main(venue["is_available"] if venue else True))
    await state.clear()


@admin_router.message(F.text == "🔙 Назад")
async def go_back(msg: Message, state: FSMContext):
    await state.clear()
    venue = await get_venue_admin(msg.from_user.id)
    avail = venue["is_available"] if venue else True
    await msg.answer("Главное меню", reply_markup=kb_admin_main(avail))


# ── Статистика ──
@admin_router.message(F.text == "📊 Статистика")
async def admin_stats(msg: Message):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return
    all_bookings = await get_venue_bookings(venue["id"], pending_only=False)
    total     = len(all_bookings)
    confirmed = sum(1 for b in all_bookings if b["status"] == "confirmed")
    cancelled = sum(1 for b in all_bookings if b["status"] == "cancelled")
    pending   = sum(1 for b in all_bookings if b["status"] == "pending")

    await msg.answer(
        f"Статистика {venue['name']}\n\n"
        f"Всего броней: {total}\n"
        f"✅ Подтверждено: {confirmed}\n"
        f"⏳ Ожидает: {pending}\n"
        f"❌ Отменено: {cancelled}",
        reply_markup=kb_admin_main(venue["is_available"])
    )


# ── Меню: главный экран ──
@admin_router.message(F.text == "🍽️ Меню заведения")
async def menu_main(msg: Message):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return
    categories = await get_menu_categories(venue["id"])
    if not categories:
        text = "Меню пока пустое. Добавьте первую категорию:"
    else:
        lines = [f"Меню · {venue['name']}\n"]
        for cat in categories:
            items = await get_menu_items(venue["id"], cat["id"])
            avail = sum(1 for i in items if i["is_available"])
            lines.append(f"📂 {cat['name']} — {len(items)} блюд ({avail} доступно)")
        text = "\n".join(lines)
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Новая категория")],
        [KeyboardButton(text="📋 Список блюд"), KeyboardButton(text="➕ Добавить блюдо")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True)
    await msg.answer(text, reply_markup=kb)


# ── Меню: добавить категорию ──
@admin_router.message(F.text == "➕ Новая категория")
async def menu_add_cat_start(msg: Message, state: FSMContext):
    await msg.answer(
        "Введите название категории.\n\n"
        "Примеры: Горячее, Птица, Мясо, Роллы, Напитки, Десерты…"
    )
    await state.set_state(AdminState.menu_add_cat_name)

@admin_router.message(AdminState.menu_add_cat_name)
async def menu_add_cat_save(msg: Message, state: FSMContext):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return
    name = msg.text.strip()
    if not name or len(name) > 50:
        await msg.answer("Название должно быть от 1 до 50 символов. Попробуйте снова:")
        return
    cat = await create_menu_category(venue["id"], name)
    await state.clear()
    if cat:
        await msg.answer(f"Категория «{name}» создана ✅")
    else:
        await msg.answer("Ошибка при создании. Попробуйте ещё раз.")
    await menu_main(msg)


# ── Меню: список блюд ──
@admin_router.message(F.text == "📋 Список блюд")
async def menu_list_dishes(msg: Message):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return
    categories = await get_menu_categories(venue["id"])
    if not categories:
        await msg.answer("Категорий нет. Сначала добавьте категорию.")
        return
    for cat in categories:
        items = await get_menu_items(venue["id"], cat["id"])
        if not items:
            await msg.answer(f"📂 {cat['name']} — пусто")
            continue
        lines = [f"📂 {cat['name']}:\n"]
        for it in items:
            status = "✅" if it["is_available"] else "⏸"
            tags = ("🔥" if it.get("is_hit") else "") + ("🆕" if it.get("is_new") else "")
            media = " [GIF]" if it.get("media_type") == "gif" else ""
            price_fmt = f"{it['price']:,}".replace(",", " ")
            lines.append(f"{status} {it['name']} {tags}{media}\n   {price_fmt} ₸  |  /dish_{it['id']}")
        await msg.answer("\n".join(lines))
    await msg.answer("Нажмите /dish_ID чтобы управлять блюдом")


# ── Меню: управление одним блюдом ──
@admin_router.message(F.text.regexp(r'^/dish_\d+$'))
async def menu_dish_control(msg: Message):
    item_id = int(msg.text.split("_")[1])
    item = await get_menu_item(item_id)
    if not item:
        await msg.answer("Блюдо не найдено.")
        return
    status = "✅ Доступно" if item["is_available"] else "⏸ Недоступно"
    price_fmt = f"{item['price']:,}".replace(",", " ")
    text = (
        f"{item['name']}\n"
        f"Цена: {price_fmt} ₸\n"
        f"Описание: {item.get('description') or '—'}\n"
        f"Медиа: {item.get('media_type', '—').upper()}\n"
        f"Статус: {status}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="⏸ Остановить" if item["is_available"] else "▶️ Включить",
            callback_data=f"dish_toggle_{item_id}"
        ),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"dish_del_{item_id}")
    ]])
    await msg.answer(text, reply_markup=kb)

@admin_router.callback_query(F.data.startswith("dish_toggle_"))
async def cb_dish_toggle(cb: CallbackQuery):
    item_id = int(cb.data.split("_")[2])
    new_val = await toggle_item_availability(item_id)
    status = "✅ Доступно" if new_val else "⏸ Приостановлено"
    await cb.message.edit_text(cb.message.text + f"\n\n→ {status}")
    await cb.answer(f"Статус: {status}")

@admin_router.callback_query(F.data.startswith("dish_del_"))
async def cb_dish_delete(cb: CallbackQuery):
    item_id = int(cb.data.split("_")[2])
    ok = await delete_menu_item(item_id)
    if ok:
        await cb.message.edit_text(cb.message.text + "\n\n🗑 Удалено")
        await cb.answer("Блюдо удалено")
    else:
        await cb.answer("Ошибка удаления", show_alert=True)


# ── Меню: добавить блюдо (пошаговый FSM) ──
@admin_router.message(F.text == "➕ Добавить блюдо")
async def menu_add_dish_start(msg: Message, state: FSMContext):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return
    cats = await get_menu_categories(venue["id"])
    if not cats:
        await msg.answer("Сначала создайте хотя бы одну категорию.")
        return
    lines = ["В какую категорию добавить блюдо?\n"]
    for cat in cats:
        lines.append(f"/cat_{cat['id']}  {cat['name']}")
    await msg.answer("\n".join(lines))
    await state.set_state(AdminState.menu_add_dish_cat)
    await state.update_data(venue_id=venue["id"])

@admin_router.message(F.text.regexp(r'^/cat_\d+$'), AdminState.menu_add_dish_cat)
async def menu_add_dish_cat(msg: Message, state: FSMContext):
    cat_id = int(msg.text.split("_")[1])
    await state.update_data(category_id=cat_id)
    await msg.answer("Введите название блюда:")
    await state.set_state(AdminState.menu_add_dish_name)

@admin_router.message(AdminState.menu_add_dish_name)
async def menu_add_dish_name(msg: Message, state: FSMContext):
    if not msg.text.strip():
        await msg.answer("Название не может быть пустым:")
        return
    await state.update_data(name=msg.text.strip())
    await msg.answer("Введите цену в тенге (только цифры, например: 2500):")
    await state.set_state(AdminState.menu_add_dish_price)

@admin_router.message(AdminState.menu_add_dish_price)
async def menu_add_dish_price(msg: Message, state: FSMContext):
    try:
        price = int(msg.text.strip().replace(" ", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await msg.answer("Введите корректную цену (например: 2500):")
        return
    await state.update_data(price=price)
    await msg.answer("Введите состав/описание (или отправьте — чтобы пропустить):")
    await state.set_state(AdminState.menu_add_dish_desc)

@admin_router.message(AdminState.menu_add_dish_desc)
async def menu_add_dish_desc(msg: Message, state: FSMContext):
    desc = "" if msg.text.strip() == "—" else msg.text.strip()
    data = await state.get_data()
    await state.clear()
    item = await create_menu_item({
        "venue_id":    data["venue_id"],
        "category_id": data["category_id"],
        "name":        data["name"],
        "price":       data["price"],
        "description": desc,
        "media_type":  "jpg",
        "is_hit":      False,
        "is_new":      False,
    })
    if item:
        price_fmt = f"{item['price']:,}".replace(",", " ")
        await msg.answer(
            f"Блюдо добавлено ✅\n\n"
            f"{item['name']} — {price_fmt} ₸\n\n"
            f"Фото/GIF можно добавить через мини-приложение.\n"
            f"Управление: /dish_{item['id']}"
        )
    else:
        await msg.answer("Ошибка при сохранении. Попробуйте снова.")
    await menu_main(msg)


# ── Уведомления клиентам ──
async def notify_venue_new_booking(booking_data: dict):
    """Уведомить администратора заведения о новой брони (вызывается из bot.py)."""
    venue = await get_venue(booking_data.get("venueId"))
    if not venue or not venue.get("admin_telegram_id"):
        return

    from database import get_venue_bookings
    try:
        bookings = await get_venue_bookings(venue["id"], pending_only=True)
        bid = bookings[0]["id"] if bookings else 0
        text = (
            f"Новая бронь!\n\n"
            f"Гость: {booking_data.get('name', 'Гость')}\n"
            f"Телефон: {booking_data.get('phone', '—')}\n"
            f"Дата: {booking_data.get('date')}, {booking_data.get('time')}\n"
            f"Гостей: {booking_data.get('guests')}\n"
            f"Зона: {booking_data.get('zone', '—')}\n"
            f"Пожелания: {booking_data.get('wishes') or '—'}"
        )
        await admin_bot.send_message(
            venue["admin_telegram_id"], text,
            reply_markup=kb_booking_actions(bid)
        )
    except Exception as e:
        logger.error(f"notify_venue_new_booking error: {e}")


async def notify_user_confirmed(booking_id: int):
    """Уведомить клиента о подтверждении."""
    try:
        from database import supabase
        from bot import bot
        b = supabase.table("bookings").select("*, venues(name, emoji)").eq("id", booking_id).single().execute().data
        if not b:
            return
        v = b.get("venues") or {}
        await bot.send_message(
            b["user_telegram_id"],
            f"Бронь подтверждена!\n\n"
            f"{v.get('emoji','')} {v.get('name','')}\n"
            f"📅 {b['booking_date']}, {b['booking_time']}\n"
            f"👥 {b['guests_count']} гостей\n\n"
            f"Ждём вас! Приятного вечера 😊"
        )
    except Exception as e:
        logger.error(f"notify_user_confirmed error: {e}")


async def notify_user_cancelled(booking_id: int):
    """Уведомить клиента об отмене."""
    try:
        from database import supabase
        from bot import bot
        b = supabase.table("bookings").select("*, venues(name)").eq("id", booking_id).single().execute().data
        if not b:
            return
        v = b.get("venues") or {}
        await bot.send_message(
            b["user_telegram_id"],
            f"К сожалению, заведение {v.get('name','')} не смогло принять вашу бронь.\n\n"
            f"Попробуйте выбрать другое время или заведение — нажмите /start"
        )
    except Exception as e:
        logger.error(f"notify_user_cancelled error: {e}")
