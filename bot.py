import json
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, MINIAPP_URL
from database import (
    upsert_user, get_user, set_consent, set_user_lang, set_user_city,
    get_user_bookings, create_booking, get_venues
)
from claude_agent import chat_with_claude, build_venues_context
from menu import save_preorder, format_preorder_text

logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)


# ══════════════════════════════════════════
# ЛОКАЛИЗАЦИЯ
# ══════════════════════════════════════════

LANGS = {
    "🇷🇺 Русский":  "ru",
    "🇰🇿 Қазақша": "kz",
    "🇬🇧 English":  "en",
}

CITIES = ["🏙 Алматы", "🏛 Астана", "🌆 Шымкент", "🌇 Другой город"]

T = {
    "ru": {
        "welcome":        lambda name: f"Добро пожаловать в Reserva, {name}! 🍽\n\nПомогу найти идеальное место и забронировать стол.\n\nИногда присылаем полезные предложения от партнёров. Хотите получать?",
        "welcome_back":   lambda name: f"С возвращением, {name}! 👋",
        "consent_yes":    "✅ Да, хочу получать предложения",
        "consent_no":     "❌ Нет, спасибо",
        "consent_ok":     "Отлично! Будем присылать только самое интересное 😊\n\nЧем могу помочь?",
        "consent_skip":   "Хорошо, без рассылки 👍\n\nЧем могу помочь?",
        "find":           "🍽️ Найти заведение",
        "my_bookings":    "📋 Мои брони",
        "about":          "ℹ️ О сервисе",
        "home":           "🏠 Главное меню",
        "settings":       "⚙️ Язык / Город",
        "choose_lang":    "Выберите язык:",
        "choose_city":    "Выберите город:",
        "lang_saved":     "Язык сохранён ✅",
        "city_saved":     lambda c: f"Город: {c} ✅",
        "start_search":   "Давайте подберём идеальное место! 🎯\nКакой формат вечера планируете?",
        "types":          ["🍽️ Ресторан", "☕ Кафе", "💨 Кальянная", "🎤 Каракое", "🎲 Помогите выбрать"],
        "no_bookings":    "У вас пока нет бронирований.\nНажмите «Найти заведение», чтобы начать!",
        "bookings_title": "Ваши бронирования:\n",
        "about_text":     "Reserva — бронирование столиков\n\nРестораны · Кафе · Кальянные · Каракое\n\nСервис бесплатен для гостей 😊",
        "booking_sent":   lambda d: f"Бронирование отправлено!\n\n{d['venueName']}\n📅 {d['date']}, {d['time']}\n👥 {d['guests']} гостей",
        "booking_wait":   "Заведение подтвердит в течение 15 минут.",
        "open_app":       "📱 Открыть приложение",
        "error":          "Что-то пошло не так. Попробуйте снова.",
        "status": {"pending": "⏳ Ожидает", "confirmed": "✅ Подтверждено", "cancelled": "❌ Отменено", "completed": "🏁 Завершено"},
    },
    "kz": {
        "welcome":        lambda name: f"Reserva-ға қош келдіңіз, {name}! 🍽\n\nТамаша орын табуға және үстел брондауға көмектесемін.\n\nКейде серіктестерден ұсыныстар жібереміз. Алғыңыз келе ме?",
        "welcome_back":   lambda name: f"Қайта келдіңіз, {name}! 👋",
        "consent_yes":    "✅ Иә, ұсыныстар алғым келеді",
        "consent_no":     "❌ Жоқ, рахмет",
        "consent_ok":     "Тамаша! Тек қызықты нәрселерді жібереміз 😊\n\nҚалай көмектесе аламын?",
        "consent_skip":   "Жақсы, хабарламасыз 👍\n\nҚалай көмектесе аламын?",
        "find":           "🍽️ Мекеме табу",
        "my_bookings":    "📋 Менің броньдарым",
        "about":          "ℹ️ Қызмет туралы",
        "home":           "🏠 Басты мәзір",
        "settings":       "⚙️ Тіл / Қала",
        "choose_lang":    "Тілді таңдаңыз:",
        "choose_city":    "Қаланы таңдаңыз:",
        "lang_saved":     "Тіл сақталды ✅",
        "city_saved":     lambda c: f"Қала: {c} ✅",
        "start_search":   "Тамаша орын табайық! 🎯\nКешкі демалысыңыздың форматы қандай?",
        "types":          ["🍽️ Мейрамхана", "☕ Кафе", "💨 Кальян", "🎤 Кара-оке", "🎲 Таңдауға көмек"],
        "no_bookings":    "Сізде әлі броньдар жоқ.\n«Мекеме табу» батырмасын басыңыз!",
        "bookings_title": "Сіздің броньдарыңыз:\n",
        "about_text":     "Reserva — үстел брондау қызметі\n\nМейрамханалар · Кафелер · Кальяндар · Кара-оке\n\nҚызмет қонақтар үшін тегін 😊",
        "booking_sent":   lambda d: f"Бронь жіберілді!\n\n{d['venueName']}\n📅 {d['date']}, {d['time']}\n👥 {d['guests']} қонақ",
        "booking_wait":   "Мекеме 15 минут ішінде растайды.",
        "open_app":       "📱 Қолданбаны ашу",
        "error":          "Бірдеңе дұрыс болмады. Қайталап көріңіз.",
        "status": {"pending": "⏳ Күтуде", "confirmed": "✅ Расталды", "cancelled": "❌ Болдырылмады", "completed": "🏁 Аяқталды"},
    },
    "en": {
        "welcome":        lambda name: f"Welcome to Reserva, {name}! 🍽\n\nI'll help you find the perfect spot and book a table.\n\nWe occasionally send useful offers from partners. Would you like to receive them?",
        "welcome_back":   lambda name: f"Welcome back, {name}! 👋",
        "consent_yes":    "✅ Yes, send me offers",
        "consent_no":     "❌ No, thanks",
        "consent_ok":     "Great! Only the best stuff 😊\n\nHow can I help?",
        "consent_skip":   "Got it, no newsletters 👍\n\nHow can I help?",
        "find":           "🍽️ Find a venue",
        "my_bookings":    "📋 My bookings",
        "about":          "ℹ️ About",
        "home":           "🏠 Main menu",
        "settings":       "⚙️ Language / City",
        "choose_lang":    "Choose your language:",
        "choose_city":    "Choose your city:",
        "lang_saved":     "Language saved ✅",
        "city_saved":     lambda c: f"City: {c} ✅",
        "start_search":   "Let's find the perfect place! 🎯\nWhat kind of evening are you planning?",
        "types":          ["🍽️ Restaurant", "☕ Café", "💨 Hookah lounge", "🎤 Karaoke", "🎲 Help me choose"],
        "no_bookings":    "No bookings yet.\nPress «Find a venue» to start!",
        "bookings_title": "Your bookings:\n",
        "about_text":     "Reserva — table booking service\n\nRestaurants · Cafés · Hookah · Karaoke\n\nFree for guests 😊",
        "booking_sent":   lambda d: f"Booking sent!\n\n{d['venueName']}\n📅 {d['date']}, {d['time']}\n👥 {d['guests']} guests",
        "booking_wait":   "The venue will confirm within 15 minutes.",
        "open_app":       "📱 Open app",
        "error":          "Something went wrong. Please try again.",
        "status": {"pending": "⏳ Pending", "confirmed": "✅ Confirmed", "cancelled": "❌ Cancelled", "completed": "🏁 Completed"},
    },
}

def t(user: dict, key: str, *args):
    lang = (user or {}).get("lang") or "ru"
    if lang not in T:
        lang = "ru"
    val = T[lang].get(key) or T["ru"].get(key, key)
    return val(*args) if callable(val) else val

def all_texts(key: str) -> set:
    """Все варианты строки на всех языках — для F.text.in_()"""
    result = set()
    for lang_dict in T.values():
        v = lang_dict.get(key)
        if v and not callable(v):
            result.add(v)
    return result


# ══════════════════════════════════════════
# СОСТОЯНИЯ
# ══════════════════════════════════════════

class S(StatesGroup):
    pick_lang   = State()
    pick_city   = State()
    consent     = State()
    chatting    = State()
    change_lang = State()
    change_city = State()


# ══════════════════════════════════════════
# КЛАВИАТУРЫ
# ══════════════════════════════════════════

def kb_lang():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=lbl)] for lbl in LANGS],
        resize_keyboard=True, one_time_keyboard=True
    )

def kb_city():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=c)] for c in CITIES],
        resize_keyboard=True, one_time_keyboard=True
    )

def kb_consent(user: dict):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t(user, "consent_yes"))],
        [KeyboardButton(text=t(user, "consent_no"))]
    ], resize_keyboard=True, one_time_keyboard=True)

def kb_main(user: dict):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t(user, "find"))],
        [KeyboardButton(text=t(user, "my_bookings")),
         KeyboardButton(text=t(user, "about"))],
        [KeyboardButton(text=t(user, "settings"))]
    ], resize_keyboard=True)

def kb_options(options: list, home_text: str):
    rows = [[KeyboardButton(text=o)] for o in options]
    rows.append([KeyboardButton(text=home_text)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def kb_open_app(user: dict, params: dict = None):
    lang = (user or {}).get("lang", "ru")
    all_params = {**(params or {}), "lang": lang}
    qs = "&".join(f"{k}={v}" for k, v in all_params.items() if v)
    url = f"{MINIAPP_URL}?{qs}" if qs else MINIAPP_URL
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(user, "open_app"), web_app=WebAppInfo(url=url))
    ]])


# ══════════════════════════════════════════
# /start
# ══════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    user = await get_user(msg.from_user.id)

    if user and user.get("lang") and user.get("city"):
        name = msg.from_user.first_name or "Гость"
        await msg.answer(t(user, "welcome_back", name), reply_markup=kb_main(user))
        return

    await upsert_user(msg.from_user.id, {
        "first_name":        msg.from_user.first_name or "",
        "last_name":         msg.from_user.last_name or "",
        "username":          msg.from_user.username or "",
        "marketing_consent": False,
        "lang":              None,
        "city":              None,
    })
    await msg.answer(
        "Привет! · Сәлем! · Hello!\n\n"
        "Выберите язык · Тілді таңдаңыз · Choose language:",
        reply_markup=kb_lang()
    )
    await state.set_state(S.pick_lang)


@router.message(S.pick_lang)
async def handle_pick_lang(msg: Message, state: FSMContext):
    lang_code = LANGS.get(msg.text)
    if not lang_code:
        await msg.answer(
            "Выберите из списка · Тізімнен таңдаңыз · Choose from the list:",
            reply_markup=kb_lang()
        )
        return
    await set_user_lang(msg.from_user.id, lang_code)
    user = await get_user(msg.from_user.id)
    await msg.answer(t(user, "choose_city"), reply_markup=kb_city())
    await state.set_state(S.pick_city)


@router.message(S.pick_city)
async def handle_pick_city(msg: Message, state: FSMContext):
    if msg.text not in CITIES:
        user = await get_user(msg.from_user.id)
        await msg.answer(t(user, "choose_city"), reply_markup=kb_city())
        return
    city_clean = msg.text.split(" ", 1)[1] if " " in msg.text else msg.text
    await set_user_city(msg.from_user.id, city_clean)
    user = await get_user(msg.from_user.id)
    name = msg.from_user.first_name or "Гость"
    await msg.answer(t(user, "welcome", name), reply_markup=kb_consent(user))
    await state.set_state(S.consent)


@router.message(S.consent)
async def handle_consent(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    consent = "✅" in msg.text
    await set_consent(msg.from_user.id, consent)
    await msg.answer(
        t(user, "consent_ok") if consent else t(user, "consent_skip"),
        reply_markup=kb_main(user)
    )
    await state.clear()


# ══════════════════════════════════════════
# НАСТРОЙКИ
# ══════════════════════════════════════════

@router.message(F.text.in_(all_texts("settings")))
async def open_settings(msg: Message, state: FSMContext):
    await state.clear()
    user = await get_user(msg.from_user.id)
    await msg.answer(t(user, "choose_lang"), reply_markup=kb_lang())
    await state.set_state(S.change_lang)

@router.message(S.change_lang)
async def settings_change_lang(msg: Message, state: FSMContext):
    lang_code = LANGS.get(msg.text)
    if not lang_code:
        await msg.answer("Выберите из списка:", reply_markup=kb_lang())
        return
    await set_user_lang(msg.from_user.id, lang_code)
    user = await get_user(msg.from_user.id)
    await msg.answer(
        t(user, "lang_saved") + "\n\n" + t(user, "choose_city"),
        reply_markup=kb_city()
    )
    await state.set_state(S.change_city)

@router.message(S.change_city)
async def settings_change_city(msg: Message, state: FSMContext):
    if msg.text not in CITIES:
        user = await get_user(msg.from_user.id)
        await msg.answer(t(user, "choose_city"), reply_markup=kb_city())
        return
    city_clean = msg.text.split(" ", 1)[1] if " " in msg.text else msg.text
    await set_user_city(msg.from_user.id, city_clean)
    user = await get_user(msg.from_user.id)
    await msg.answer(t(user, "city_saved", city_clean), reply_markup=kb_main(user))
    await state.clear()


# ══════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ══════════════════════════════════════════

@router.message(F.text.in_(all_texts("home")))
async def go_home(msg: Message, state: FSMContext):
    await state.clear()
    user = await get_user(msg.from_user.id)
    await msg.answer(t(user, "home"), reply_markup=kb_main(user))

@router.message(F.text.in_(all_texts("find")))
async def find_venue(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    await state.set_state(S.chatting)
    await state.update_data(
        history=[],
        collected={"type": None, "guests": None, "date": None, "time": None}
    )
    await msg.answer(
        t(user, "start_search"),
        reply_markup=kb_options(t(user, "types"), t(user, "home"))
    )

@router.message(F.text.in_(all_texts("my_bookings")))
async def my_bookings(msg: Message):
    user = await get_user(msg.from_user.id)
    bookings = await get_user_bookings(msg.from_user.id)
    if not bookings:
        await msg.answer(t(user, "no_bookings"), reply_markup=kb_main(user))
        return
    statuses = t(user, "status")
    lines = [t(user, "bookings_title")]
    for b in bookings[:5]:
        v = b.get("venues") or {}
        lines.append(
            f"{v.get('emoji','')} {v.get('name','')}\n"
            f"  {b.get('booking_date')}, {b.get('booking_time')}\n"
            f"  {b.get('guests_count')} | {statuses.get(b['status'], b['status'])}\n"
        )
    await msg.answer("\n".join(lines), reply_markup=kb_main(user))

@router.message(F.text.in_(all_texts("about")))
async def about(msg: Message):
    user = await get_user(msg.from_user.id)
    await msg.answer(t(user, "about_text"), reply_markup=kb_main(user))


# ══════════════════════════════════════════
# ДИАЛОГ С CLAUDE
# ══════════════════════════════════════════

@router.message(S.chatting)
async def handle_chat(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    data = await state.get_data()
    history   = data.get("history", [])
    collected = data.get("collected", {"type": None, "guests": None, "date": None, "time": None})

    await bot.send_chat_action(msg.chat.id, "typing")

    lang = (user or {}).get("lang", "ru")
    city = (user or {}).get("city", "Алматы")
    venues_ctx = await build_venues_context(collected.get("type"), city)

    result = await chat_with_claude(
        conversation_history=history,
        user_message=msg.text,
        collected_params=collected,
        venues_context=venues_ctx,
        lang=lang,
        city=city,
    )

    history.append({"role": "user",      "content": msg.text})
    history.append({"role": "assistant", "content": json.dumps(result, ensure_ascii=False)})
    history = history[-20:]

    if result.get("collected"):
        for k, v in result["collected"].items():
            if v is not None:
                collected[k] = v

    await state.update_data(history=history, collected=collected)

    reply_text = result.get("message", "")

    if result.get("show_venues"):
        venues_list = await _format_venues(collected)
        if venues_list:
            reply_text = reply_text + "\n\n" + venues_list

    if result.get("ready_to_book"):
        await msg.answer(reply_text, reply_markup=kb_main(user))
        await msg.answer(
            reply_text,
            reply_markup=kb_open_app(user, {
                "type":   collected.get("type", ""),
                "guests": collected.get("guests", ""),
                "date":   collected.get("date", ""),
                "time":   collected.get("time", ""),
                "city":   city,
            })
        )
    elif result.get("quick_replies"):
        await msg.answer(
            reply_text,
            reply_markup=kb_options(result["quick_replies"], t(user, "home"))
        )
    else:
        await msg.answer(reply_text, reply_markup=kb_main(user))


async def _format_venues(collected: dict) -> str:
    type_map = {
        "ресторан": "restaurant", "кафе": "cafe", "кальянная": "hookah", "каракое": "karaoke",
        "мейрамхана": "restaurant", "кальян": "hookah", "кара-оке": "karaoke",
        "restaurant": "restaurant", "café": "cafe", "cafe": "cafe",
        "hookah lounge": "hookah", "hookah": "hookah", "karaoke": "karaoke",
    }
    tf = type_map.get((collected.get("type") or "").lower())
    venues = await get_venues(tf, available_only=True)
    if not venues:
        return ""
    lines = []
    for v in venues[:4]:
        check_from = v.get("avg_check", "").split("–")[0]
        lines.append(
            f"{v.get('emoji','')} {v['name']}\n"
            f"  📍 {v.get('address','')}\n"
            f"  ⭐ {v.get('rating','')} · {check_from}\n"
        )
    return "\n".join(lines)


# ══════════════════════════════════════════
# ДАННЫЕ ИЗ МИНИ-АПП
# ══════════════════════════════════════════

@router.message(F.web_app_data)
async def handle_webapp_data(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    try:
        data = json.loads(msg.web_app_data.data)
        action = data.get("action")

        if action == "booking":
            booking_result = await create_booking({
                "user_telegram_id": msg.from_user.id,
                "venue_id":         data.get("venueId"),
                "guest_name":       data.get("name"),
                "phone":            data.get("phone"),
                "booking_date":     data.get("date"),
                "booking_time":     data.get("time"),
                "guests_count":     int(data.get("guests", 2)),
                "zone":             data.get("zone"),
                "wishes":           data.get("wishes", ""),
            })
            booking_id = booking_result.data[0]["id"] if booking_result.data else None

            preorder_text = ""
            if booking_id and data.get("preorder"):
                await save_preorder(booking_id, data["preorder"])
                preorder_text = await format_preorder_text(booking_id)

            await msg.answer(
                t(user, "booking_sent", data) + preorder_text + "\n\n" + t(user, "booking_wait"),
                reply_markup=kb_main(user)
            )
            try:
                from admin_bot import notify_venue_new_booking
                await notify_venue_new_booking({**data, "booking_id": booking_id})
            except Exception as e:
                logger.error(f"Failed to notify venue: {e}")

        elif action == "preorder":
            booking_id = data.get("bookingId")
            if booking_id:
                await save_preorder(booking_id, data.get("items", []))
                preorder_text = await format_preorder_text(booking_id)
                await msg.answer(f"✅ {preorder_text}", reply_markup=kb_main(user))

    except Exception as e:
        logger.error(f"WebApp data error: {e}")
        await msg.answer(t(user, "error"), reply_markup=kb_main(user))
