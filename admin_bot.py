"""
admin_bot.py — Партнёрский бот Reserva
Полная автоматическая регистрация заведений:
  1. Выбор языка 🇷🇺 🇰🇿 🇬🇧
  2. Принятие оферты и ПК
  3. Ввод БИН → проверка через ГБД ЮЛ РК
  4. Анкета заведения
  5. Загрузка фото
  6. Выбор тарифа (со счётчиком акции 50 мест -50%)
  7. Реферальный код
  8. Оплата через Robokassa
  9. Уведомление владельцу → одобрение/отклонение
"""
 
import logging
import hashlib
from urllib.parse import quote
 
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
 
from config import (
    ADMIN_BOT_TOKEN, OWNER_ID, PLANS,
    PROMO_DISCOUNT, PROMO_MONTHS,
    TERMS_URL, PRIVACY_URL,
    ROBOKASSA_LOGIN, ROBOKASSA_PASS1, ROBOKASSA_TEST,
)
from database import (
    get_venue_admin, update_venue,
    get_venue_bookings, update_booking_status, get_venue,
    get_user, upsert_user, set_user_lang,
    create_venue_application, update_venue_application,
    get_venue_application,
    approve_venue_application, reject_venue_application,
    get_promo_slots_left, use_promo_slot,
    get_or_create_referral_code, get_referral_by_code,
    get_referral_stats,
)
from menu import (
    get_menu_categories, create_menu_category,
    get_menu_items, get_menu_item, create_menu_item,
    delete_menu_item, toggle_item_availability,
)
 
logger = logging.getLogger(__name__)
 
admin_bot = Bot(token=ADMIN_BOT_TOKEN)
admin_storage = MemoryStorage()
admin_dp = Dispatcher(storage=admin_storage)
admin_router = Router()
admin_dp.include_router(admin_router)
 
 
# ══════════════════════════════════════════
# ЛОКАЛИЗАЦИЯ
# ══════════════════════════════════════════
 
ADMIN_LANGS = {
    "🇷🇺 Русский":  "ru",
    "🇰🇿 Қазақша": "kz",
    "🇬🇧 English":  "en",
}
 
VENUE_TYPES = {
    "ru": [
        ("🍽️ Ресторан",   "restaurant"),
        ("☕ Кафе",        "cafe"),
        ("💨 Кальянная",  "hookah"),
        ("🎤 Каракое",    "karaoke"),
        ("🎱 Бильярдная", "billiard"),
        ("🍺 Бар",        "bar"),
    ],
    "kz": [
        ("🍽️ Мейрамхана", "restaurant"),
        ("☕ Кафе",        "cafe"),
        ("💨 Кальян",     "hookah"),
        ("🎤 Кара-оке",   "karaoke"),
        ("🎱 Бильярд",    "billiard"),
        ("🍺 Бар",        "bar"),
    ],
    "en": [
        ("🍽️ Restaurant", "restaurant"),
        ("☕ Café",        "cafe"),
        ("💨 Hookah",     "hookah"),
        ("🎤 Karaoke",    "karaoke"),
        ("🎱 Billiards",  "billiard"),
        ("🍺 Bar",        "bar"),
    ],
}
 
CITIES = {
    "ru": ["🏙 Алматы", "🏛 Астана", "🌆 Шымкент", "🌇 Другой город"],
    "kz": ["🏙 Алматы", "🏛 Астана", "🌆 Шымкент", "🌇 Басқа қала"],
    "en": ["🏙 Almaty",  "🏛 Astana", "🌆 Shymkent", "🌇 Other city"],
}
 
T = {
    "ru": {
        "choose_lang":   "Выберите язык кабинета:",
        "lang_saved":    "Язык сохранён ✅",
        "welcome_new":   "Добро пожаловать в Reserva Partner! 🍽\n\nЗарегистрируйте своё заведение и начните получать брони от тысяч клиентов Алматы и Астаны.",
        "terms_prompt":  lambda tu, pu: f"Перед регистрацией ознакомьтесь с документами:\n\n📄 <a href='{tu}'>Публичная оферта</a>\n🔒 <a href='{pu}'>Политика конфиденциальности</a>",
        "terms_accept":  "✅ Принимаю условия и регистрируюсь",
        "terms_decline": "❌ Не принимаю",
        "terms_declined":"Без принятия условий регистрация невозможна.\nНапишите /start чтобы начать заново.",
        "enter_bin":     "Введите ИИН/БИН (12 цифр):",
        "bin_checking":  "🔍 Проверяю БИН в реестре РК...",
        "bin_invalid":   "БИН должен содержать ровно 12 цифр. Попробуйте ещё раз:",
        "bin_not_found": "❌ Организация с таким БИН не найдена в реестре РК.\nПроверьте правильность ввода.",
        "bin_inactive":  "❌ Организация не активна или ликвидирована.\nРегистрация невозможна.",
        "bin_okved_fail":"❌ Вид деятельности вашей организации (ОКЭД) не соответствует профилю общепита.\nСвяжитесь с поддержкой: @reserva_support",
        "bin_ok":        lambda n, o: f"✅ Организация найдена!\n\n🏢 {n}\n📋 ОКЭД: {o}\n\nВсё верно?",
        "bin_confirm":   "✅ Да, всё верно",
        "bin_reenter":   "🔄 Ввести другой БИН",
        "enter_brand":   "Введите название вашего заведения (бренд):\n\n_Может отличаться от юридического названия_",
        "choose_type":   "Выберите тип заведения:",
        "enter_city":    "Выберите город:",
        "enter_address": "Введите фактический адрес заведения:",
        "enter_phone":   "Введите контактный телефон заведения:",
        "enter_hours":   "Введите часы работы:\n\nПример: Пн-Пт 10:00-23:00, Сб-Вс 11:00-00:00",
        "enter_check":   "Введите средний чек на человека:\n\nПример: 3 000–7 000 ₸",
        "enter_desc":    "Кратко опишите ваше заведение (2-3 предложения):\n\nЭто увидят клиенты в приложении.",
        "enter_video":   "Отправьте ссылку на видео заведения (YouTube, TikTok, Instagram)\nили нажмите «Пропустить»:",
        "skip":          "⏭️ Пропустить",
        "enter_photos":  "Отправьте фотографии заведения (до 5 штук).\n\nОтправляйте по одной фотографии. Когда закончите — нажмите «Готово».",
        "photos_done":   "✅ Готово, продолжить",
        "photo_added":   lambda n: f"📸 Фото {n}/5 добавлено ✅\nОтправьте ещё или нажмите «Готово».",
        "photos_max":    "Максимум 5 фотографий. Нажмите «Готово».",
        "choose_plan":   "Выберите тарифный план:",
        "promo_active":  lambda l: f"🔥 АКЦИЯ! Осталось {l} мест из 50\nСкидка 50% на первые 3 месяца!",
        "promo_ended":   "Акционные места закончились. Доступны стандартные тарифы.",
        "enter_ref":     "Есть реферальный код партнёра?\nВведите его или нажмите «Пропустить»:",
        "ref_valid":     "Реферальный код принят! 🤝",
        "ref_invalid":   "Код не найден. Продолжаем без реферала.",
        "summary":       "📋 Проверьте данные заявки:",
        "confirm_send":  "✅ Отправить заявку",
        "edit":          "✏️ Изменить данные",
        "app_sent":      "🎉 Заявка отправлена!\n\nМы проверим данные и свяжемся с вами в течение 24 часов.",
        "approved":      "🎉 Поздравляем! Ваше заведение одобрено!\n\nОплатите тариф для активации:",
        "rejected":      lambda r: f"❌ К сожалению, заявка отклонена.\nПричина: {r}\n\nСвяжитесь с поддержкой: @reserva_support",
        "pay_now":       "💳 Оплатить сейчас",
        "pay_later":     "⏰ Оплатить позже",
        "ref_code":      lambda c, n, b: f"🔗 Ваша реферальная ссылка:\nt.me/reserva_partner_bot?start=ref_{c}\n\n👥 Приглашено партнёров: {n}\n🎁 Накоплено бонусных месяцев: {b}\n\nБонусы за рефералов:\n• 1 партнёр → +1 мес бесплатно\n• 3 партнёра → +3 мес бесплатно\n• 5 партнёров → +6 мес бесплатно\n\nПоделитесь ссылкой с коллегами!",
        "no_venue":      "Ваше заведение ещё не зарегистрировано.\nНажмите «Зарегистрировать заведение».",
        "not_connected": "Добро пожаловать в Reserva Partner! 🍽\n\nДля начала зарегистрируйте своё заведение.",
        "register_btn":  "📝 Зарегистрировать заведение",
        "lang_btn":      "⚙️ Язык",
    },
    "kz": {
        "choose_lang":   "Кабинет тілін таңдаңыз:",
        "lang_saved":    "Тіл сақталды ✅",
        "welcome_new":   "Reserva Partner-ге қош келдіңіз! 🍽\n\nМекемеңізді тіркеп, мыңдаған клиенттерден брондаулар алуды бастаңыз.",
        "terms_prompt":  lambda tu, pu: f"Тіркелмес бұрын құжаттармен танысыңыз:\n\n📄 <a href='{tu}'>Жария оферта</a>\n🔒 <a href='{pu}'>Құпиялылық саясаты</a>",
        "terms_accept":  "✅ Шарттарды қабылдаймын",
        "terms_decline": "❌ Қабылдамаймын",
        "terms_declined":"Шарттарды қабылдаусыз тіркелу мүмкін емес.\n/start жазып қайтадан бастаңыз.",
        "enter_bin":     "ИИН/БИН енгізіңіз (12 сан):",
        "bin_checking":  "🔍 БИН РК тізілімінде тексерілуде...",
        "bin_invalid":   "БИН 12 саннан тұруы керек. Қайталап көріңіз:",
        "bin_not_found": "❌ Бұл БИН бар ұйым РК тізілімінде табылмады.",
        "bin_inactive":  "❌ Ұйым белсенді емес немесе таратылған.",
        "bin_okved_fail":"❌ Ұйымның қызмет түрі қоғамдық тамақтану профиліне сәйкес келмейді.",
        "bin_ok":        lambda n, o: f"✅ Ұйым табылды!\n\n🏢 {n}\n📋 ЭҚЖЖ: {o}\n\nБәрі дұрыс па?",
        "bin_confirm":   "✅ Иә, дұрыс",
        "bin_reenter":   "🔄 Басқа БИН енгізу",
        "enter_brand":   "Мекеменің атауын (брендін) енгізіңіз:",
        "choose_type":   "Мекеме түрін таңдаңыз:",
        "enter_city":    "Қаланы таңдаңыз:",
        "enter_address": "Мекеменің нақты мекенжайын енгізіңіз:",
        "enter_phone":   "Мекеменің байланыс телефонын енгізіңіз:",
        "enter_hours":   "Жұмыс уақытын енгізіңіз:",
        "enter_check":   "Бір адамға орташа есепшотты енгізіңіз:",
        "enter_desc":    "Мекемені қысқаша сипаттаңыз (2-3 сөйлем):",
        "enter_video":   "Бейне сілтемесін жіберіңіз немесе «Өткізіп жіберу» басыңыз:",
        "skip":          "⏭️ Өткізіп жіберу",
        "enter_photos":  "Мекеменің фотосуреттерін жіберіңіз (5-ке дейін).\n«Дайын» басқанда жалғасады.",
        "photos_done":   "✅ Дайын, жалғастыру",
        "photo_added":   lambda n: f"📸 Фото {n}/5 қосылды ✅",
        "photos_max":    "Максимум 5 фото. «Дайын» басыңыз.",
        "choose_plan":   "Тариф жоспарын таңдаңыз:",
        "promo_active":  lambda l: f"🔥 АКЦИЯ! {l} орын қалды 50-нен\n3 айға 50% жеңілдік!",
        "promo_ended":   "Акциялық орындар таусылды.",
        "enter_ref":     "Реферал коды бар ма? Енгізіңіз немесе өткізіп жіберіңіз:",
        "ref_valid":     "Реферал коды қабылданды! 🤝",
        "ref_invalid":   "Код табылмады. Рефералсыз жалғастырамыз.",
        "summary":       "📋 Өтінім деректерін тексеріңіз:",
        "confirm_send":  "✅ Өтінімді жіберу",
        "edit":          "✏️ Өзгерту",
        "app_sent":      "🎉 Өтінім жіберілді!\n\n24 сағат ішінде хабарласамыз.",
        "approved":      "🎉 Мекемеңіз мақұлданды!\n\nАктивтеу үшін тарифті төлеңіз:",
        "rejected":      lambda r: f"❌ Өтінім қабылданбады.\nСебебі: {r}",
        "pay_now":       "💳 Қазір төлеу",
        "pay_later":     "⏰ Кейін төлеу",
        "ref_code":      lambda c, n, b: f"🔗 Сіздің реферал сілтемеңіз:\nt.me/reserva_partner_bot?start=ref_{c}\n\n👥 Шақырылған серіктестер: {n}\n🎁 Бонустық айлар: {b}",
        "no_venue":      "Мекемеңіз әлі тіркелмеген.",
        "not_connected": "Reserva Partner-ге қош келдіңіз! 🍽\n\nМекемеңізді тіркеңіз.",
        "register_btn":  "📝 Мекемені тіркеу",
        "lang_btn":      "⚙️ Тіл",
    },
    "en": {
        "choose_lang":   "Choose cabinet language:",
        "lang_saved":    "Language saved ✅",
        "welcome_new":   "Welcome to Reserva Partner! 🍽\n\nRegister your venue and start receiving bookings.",
        "terms_prompt":  lambda tu, pu: f"Please review our documents:\n\n📄 <a href='{tu}'>Public Offer</a>\n🔒 <a href='{pu}'>Privacy Policy</a>",
        "terms_accept":  "✅ I accept and register",
        "terms_decline": "❌ I decline",
        "terms_declined":"Registration requires accepting the terms.\nType /start to begin again.",
        "enter_bin":     "Enter your IIN/BIN (12 digits):",
        "bin_checking":  "🔍 Checking BIN in RK registry...",
        "bin_invalid":   "BIN must be exactly 12 digits. Please try again:",
        "bin_not_found": "❌ Organization not found in RK registry.",
        "bin_inactive":  "❌ Organization is inactive or liquidated.",
        "bin_okved_fail":"❌ Organization activity type doesn't match food service profile.",
        "bin_ok":        lambda n, o: f"✅ Organization found!\n\n🏢 {n}\n📋 OKED: {o}\n\nIs this correct?",
        "bin_confirm":   "✅ Yes, correct",
        "bin_reenter":   "🔄 Enter different BIN",
        "enter_brand":   "Enter your venue name (brand):",
        "choose_type":   "Choose venue type:",
        "enter_city":    "Choose city:",
        "enter_address": "Enter the actual venue address:",
        "enter_phone":   "Enter venue contact phone:",
        "enter_hours":   "Enter working hours:",
        "enter_check":   "Enter average check per person:",
        "enter_desc":    "Briefly describe your venue (2-3 sentences):",
        "enter_video":   "Send video link (YouTube, TikTok, Instagram) or press Skip:",
        "skip":          "⏭️ Skip",
        "enter_photos":  "Send venue photos (up to 5). Press Done when finished.",
        "photos_done":   "✅ Done, continue",
        "photo_added":   lambda n: f"📸 Photo {n}/5 added ✅",
        "photos_max":    "Maximum 5 photos. Press Done.",
        "choose_plan":   "Choose your plan:",
        "promo_active":  lambda l: f"🔥 PROMO! {l} spots left out of 50\n50% off for first 3 months!",
        "promo_ended":   "Promo spots are gone. Standard pricing applies.",
        "enter_ref":     "Have a referral code? Enter it or press Skip:",
        "ref_valid":     "Referral code accepted! 🤝",
        "ref_invalid":   "Code not found. Continuing without referral.",
        "summary":       "📋 Review your application:",
        "confirm_send":  "✅ Submit application",
        "edit":          "✏️ Edit data",
        "app_sent":      "🎉 Application submitted!\n\nWe'll review and contact you within 24 hours.",
        "approved":      "🎉 Your venue is approved!\n\nPay to activate:",
        "rejected":      lambda r: f"❌ Application rejected.\nReason: {r}",
        "pay_now":       "💳 Pay now",
        "pay_later":     "⏰ Pay later",
        "ref_code":      lambda c, n, b: f"🔗 Your referral link:\nt.me/reserva_partner_bot?start=ref_{c}\n\n👥 Partners invited: {n}\n🎁 Bonus months: {b}",
        "no_venue":      "Your venue is not registered yet.",
        "not_connected": "Welcome to Reserva Partner! 🍽\n\nRegister your venue to get started.",
        "register_btn":  "📝 Register venue",
        "lang_btn":      "⚙️ Language",
    },
}
 
def at(lang: str, key: str, *args):
    lang = lang if lang in T else "ru"
    val = T[lang].get(key) or T["ru"].get(key, key)
    return val(*args) if callable(val) else val
 
 
# ══════════════════════════════════════════
# СОСТОЯНИЯ FSM
# ══════════════════════════════════════════
 
class AdminState(StatesGroup):
    pick_lang           = State()
    terms               = State()
    reg_bin             = State()
    reg_brand           = State()
    reg_type            = State()
    reg_city            = State()
    reg_address         = State()
    reg_phone           = State()
    reg_hours           = State()
    reg_check           = State()
    reg_desc            = State()
    reg_video           = State()
    reg_photos          = State()
    reg_plan            = State()
    reg_ref             = State()
    reg_confirm         = State()
    edit_description    = State()
    edit_avg_check      = State()
    edit_video_url      = State()
    menu_add_cat_name   = State()
    menu_add_dish_cat   = State()
    menu_add_dish_name  = State()
    menu_add_dish_price = State()
    menu_add_dish_desc  = State()
    change_lang         = State()
 
 
# ══════════════════════════════════════════
# КЛАВИАТУРЫ
# ══════════════════════════════════════════
 
def kb_lang():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=lbl)] for lbl in ADMIN_LANGS],
        resize_keyboard=True, one_time_keyboard=True
    )
 
def kb_main(lang: str, registered: bool = True):
    if registered:
        return ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🔔 Новые брони" if lang=="ru" else "🔔 Жаңа броньдар" if lang=="kz" else "🔔 New bookings")],
            [KeyboardButton(text="🍽️ Меню" if lang=="ru" else "🍽️ Мәзір" if lang=="kz" else "🍽️ Menu")],
            [KeyboardButton(text="✏️ Профиль" if lang=="ru" else "✏️ Профиль" if lang=="kz" else "✏️ Profile")],
            [KeyboardButton(text="🔄 Вкл/Выкл брони" if lang=="ru" else "🔄 Брондауды қосу/өшіру" if lang=="kz" else "🔄 Toggle bookings")],
            [KeyboardButton(text="📊 Статистика" if lang=="ru" else "📊 Статистика" if lang=="kz" else "📊 Statistics")],
            [KeyboardButton(text="🎁 Рефералы" if lang=="ru" else "🎁 Рефералдар" if lang=="kz" else "🎁 Referrals")],
            [KeyboardButton(text=at(lang, "lang_btn"))],
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text=at(lang, "register_btn"))],
            [KeyboardButton(text=at(lang, "lang_btn"))],
        ], resize_keyboard=True)
 
def kb_cities(lang: str):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=c)] for c in CITIES.get(lang, CITIES["ru"])],
        resize_keyboard=True, one_time_keyboard=True
    )
 
def kb_types(lang: str):
    types = VENUE_TYPES.get(lang, VENUE_TYPES["ru"])
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=lbl)] for lbl, _ in types],
        resize_keyboard=True, one_time_keyboard=True
    )
 
def kb_skip(lang: str):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=at(lang, "skip"))]],
        resize_keyboard=True, one_time_keyboard=True
    )
 
def kb_photos_done(lang: str):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=at(lang, "photos_done"))]],
        resize_keyboard=True
    )
 
def kb_yes_no(yes: str, no: str):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=yes)], [KeyboardButton(text=no)]],
        resize_keyboard=True, one_time_keyboard=True
    )
 
def kb_approve_reject(app_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить",  callback_data=f"approv_{app_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{app_id}"),
    ]])
 
def kb_pay(url: str, lang: str):
    rows = []
    if url:
        rows.append([InlineKeyboardButton(text=at(lang, "pay_now"), url=url)])
    rows.append([InlineKeyboardButton(text=at(lang, "pay_later"), callback_data="pay_later")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
 
def kb_plans(lang: str, promo: bool):
    rows = []
    for key, info in PLANS.items():
        price = info["price_promo"] if promo else info["price"]
        promo_tag = f" 🔥-50%" if promo else ""
        rows.append([InlineKeyboardButton(
            text=f"{info['name']} — {price} ₸/мес{promo_tag}",
            callback_data=f"plan_{key}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)
 
 
# ══════════════════════════════════════════
# БИН-ПРОВЕРКА
# ══════════════════════════════════════════
 
 
 
# ══════════════════════════════════════════
# ROBOKASSA
# ══════════════════════════════════════════
 
def generate_payment_url(amount: int, inv_id: int, description: str) -> str:
    if not ROBOKASSA_LOGIN or not ROBOKASSA_PASS1:
        return ""
    sign = hashlib.md5(
        f"{ROBOKASSA_LOGIN}:{amount}:{inv_id}:{ROBOKASSA_PASS1}".encode()
    ).hexdigest()
    test = "&IsTest=1" if ROBOKASSA_TEST == "1" else ""
    return (
        f"https://auth.robokassa.ru/Merchant/Index.aspx"
        f"?MerchantLogin={ROBOKASSA_LOGIN}"
        f"&OutSum={amount}&InvId={inv_id}"
        f"&Description={quote(description)}"
        f"&SignatureValue={sign}{test}"
    )
 
 
# ══════════════════════════════════════════
# ХЕЛПЕРЫ
# ══════════════════════════════════════════
 
async def get_lang(tg_id: int, state: FSMContext) -> str:
    d = await state.get_data()
    if d.get("lang"):
        return d["lang"]
    u = await get_user(tg_id)
    return (u or {}).get("lang", "ru") or "ru"
 
def build_summary(d: dict) -> str:
    plan_key  = d.get("plan", "start")
    plan_info = PLANS.get(plan_key, PLANS["start"])
    promo     = d.get("promo_applied", False)
    price     = plan_info["price_promo"] if promo else plan_info["price"]
    promo_tag = " (акция -50%, 3 мес)" if promo else ""
    return (
        f"🏢 {d.get('brand_name','—')}\n"
        f"📂 {d.get('venue_type_label', d.get('venue_type','—'))}\n"
        f"📍 {d.get('city','—')}, {d.get('actual_address','—')}\n"
        f"📞 {d.get('phone','—')}\n"
        f"🕐 {d.get('work_hours','—')}\n"
        f"💰 {d.get('avg_check','—')}\n"
        f"📝 {(d.get('description','—'))[:80]}…\n"
        f"📸 Фото: {len(d.get('photos',[]))} шт.\n"
        f"🎬 Видео: {'есть' if d.get('video_url') else 'нет'}\n"
        f"💳 {plan_info['name']} — {price} ₸/мес{promo_tag}\n"
        f"🔗 Реферал: {d.get('referral_code','—')}"
    )
 
 
# ══════════════════════════════════════════
# /start
# ══════════════════════════════════════════
 
@admin_router.message(CommandStart())
async def admin_start(msg: Message, state: FSMContext):
    await state.clear()
    text = msg.text or ""
    ref_code = None
    if "ref_" in text:
        parts = text.split("ref_")
        if len(parts) > 1:
            ref_code = parts[1].strip().upper()
 
    user = await get_user(msg.from_user.id)
    if not user:
        await upsert_user(msg.from_user.id, {
            "first_name": msg.from_user.first_name or "",
            "username":   msg.from_user.username or "",
            "lang":       None,
        })
 
    if ref_code:
        await state.update_data(referral_code_from_start=ref_code)
 
    if user and user.get("lang"):
        lang = user["lang"]
        venue = await get_venue_admin(msg.from_user.id)
        if venue:
            status = "✅ Приём включён" if venue["is_available"] else "⏸️ Приём остановлен"
            await msg.answer(
                f"{venue.get('emoji','')} {venue['name']}\n📍 {venue.get('address','')}\n{status}",
                reply_markup=kb_main(lang, registered=True)
            )
        else:
            await msg.answer(at(lang, "not_connected"), reply_markup=kb_main(lang, registered=False))
        return
 
    await msg.answer(
        "Привет! · Сәлем! · Hello!\n\nВыберите язык · Тілді таңдаңыз · Choose language:",
        reply_markup=kb_lang()
    )
    await state.set_state(AdminState.pick_lang)
 
 
@admin_router.message(AdminState.pick_lang)
async def pick_lang(msg: Message, state: FSMContext):
    code = ADMIN_LANGS.get(msg.text)
    if not code:
        await msg.answer("Выберите из списка:", reply_markup=kb_lang())
        return
    await set_user_lang(msg.from_user.id, code)
    await state.update_data(lang=code)
    await msg.answer(at(code, "lang_saved"))
    await msg.answer(
        at(code, "terms_prompt", TERMS_URL, PRIVACY_URL),
        parse_mode="HTML",
        reply_markup=kb_yes_no(at(code, "terms_accept"), at(code, "terms_decline"))
    )
    await state.set_state(AdminState.terms)
 
 
@admin_router.message(AdminState.terms)
async def handle_terms(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    if "✅" in msg.text:
        await state.update_data(terms_accepted=True)
        await msg.answer(at(lang, "enter_bin"), reply_markup=ReplyKeyboardRemove())
        await state.set_state(AdminState.reg_bin)
    else:
        await state.clear()
        await msg.answer(at(lang, "terms_declined"), reply_markup=ReplyKeyboardRemove())
 
 
# ══════════════════════════════════════════
# РЕГИСТРАЦИЯ
# ══════════════════════════════════════════
 
@admin_router.message(AdminState.reg_bin)
async def reg_bin_handler(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    bin_code = msg.text.strip().replace(" ", "")
    if not bin_code.isdigit() or len(bin_code) != 12:
        await msg.answer("ИИН/БИН должен содержать 12 цифр. Попробуйте ещё раз:")
        return
    # Сохраняем БИН без проверки — владелец одобряет вручную
    await state.update_data(bin=bin_code)
    await msg.answer(at(lang, "enter_brand"), reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminState.reg_brand)
 
 
@admin_router.message(AdminState.reg_brand)
async def reg_brand(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    await state.update_data(brand_name=msg.text.strip())
    await msg.answer(at(lang, "choose_type"), reply_markup=kb_types(lang))
    await state.set_state(AdminState.reg_type)
 
 
@admin_router.message(AdminState.reg_type)
async def reg_type(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    types = VENUE_TYPES.get(lang, VENUE_TYPES["ru"])
    match = next(((lbl, code) for lbl, code in types if lbl == msg.text), None)
    if not match:
        await msg.answer(at(lang, "choose_type"), reply_markup=kb_types(lang))
        return
    await state.update_data(venue_type=match[1], venue_type_label=match[0])
    await msg.answer(at(lang, "enter_city"), reply_markup=kb_cities(lang))
    await state.set_state(AdminState.reg_city)
 
 
@admin_router.message(AdminState.reg_city)
async def reg_city(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    city_clean = msg.text.split(" ", 1)[1] if " " in msg.text else msg.text
    await state.update_data(city=city_clean)
    await msg.answer(at(lang, "enter_address"), reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminState.reg_address)
 
 
@admin_router.message(AdminState.reg_address)
async def reg_address(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    await state.update_data(actual_address=msg.text.strip())
    await msg.answer(at(lang, "enter_phone"))
    await state.set_state(AdminState.reg_phone)
 
 
@admin_router.message(AdminState.reg_phone)
async def reg_phone(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    await state.update_data(phone=msg.text.strip())
    await msg.answer(at(lang, "enter_hours"))
    await state.set_state(AdminState.reg_hours)
 
 
@admin_router.message(AdminState.reg_hours)
async def reg_hours(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    await state.update_data(work_hours=msg.text.strip())
    await msg.answer(at(lang, "enter_check"))
    await state.set_state(AdminState.reg_check)
 
 
@admin_router.message(AdminState.reg_check)
async def reg_check(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    await state.update_data(avg_check=msg.text.strip())
    await msg.answer(at(lang, "enter_desc"))
    await state.set_state(AdminState.reg_desc)
 
 
@admin_router.message(AdminState.reg_desc)
async def reg_desc(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    await state.update_data(description=msg.text.strip())
    await msg.answer(at(lang, "enter_video"), reply_markup=kb_skip(lang))
    await state.set_state(AdminState.reg_video)
 
 
@admin_router.message(AdminState.reg_video)
async def reg_video(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    skip = at(lang, "skip")
    if msg.text and skip not in msg.text:
        await state.update_data(video_url=msg.text.strip())
    await state.update_data(photos=[])
    await msg.answer(at(lang, "enter_photos"), reply_markup=kb_photos_done(lang))
    await state.set_state(AdminState.reg_photos)
 
 
@admin_router.message(AdminState.reg_photos)
async def reg_photos(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    data = await state.get_data()
    photos = data.get("photos", [])
    done = at(lang, "photos_done")
 
    if msg.text and done in msg.text:
        await show_plan_selection(msg, state, lang)
        return
 
    if msg.photo:
        if len(photos) >= 5:
            await msg.answer(at(lang, "photos_max"), reply_markup=kb_photos_done(lang))
            return
        photos.append(msg.photo[-1].file_id)
        await state.update_data(photos=photos)
        await msg.answer(at(lang, "photo_added", len(photos)), reply_markup=kb_photos_done(lang))
    else:
        await msg.answer(at(lang, "enter_photos"), reply_markup=kb_photos_done(lang))
 
 
async def show_plan_selection(msg: Message, state: FSMContext, lang: str):
    slots = await get_promo_slots_left()
    promo = slots > 0
    await state.update_data(promo_available=promo, promo_slots_left=slots)
    notice = at(lang, "promo_active", slots) if promo else at(lang, "promo_ended")
    await msg.answer(notice + "\n\n" + at(lang, "choose_plan"),
                     reply_markup=ReplyKeyboardRemove())
    await msg.answer("👇", reply_markup=kb_plans(lang, promo))
    await state.set_state(AdminState.reg_plan)
 
 
@admin_router.callback_query(F.data.startswith("plan_"), AdminState.reg_plan)
async def reg_plan(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id, state)
    plan_key = cb.data[5:]
    data = await state.get_data()
    promo = data.get("promo_available", False)
    await state.update_data(plan=plan_key, promo_applied=promo)
    await cb.message.edit_reply_markup()
    await cb.answer()
 
    ref_from_start = data.get("referral_code_from_start")
    if ref_from_start:
        ref = await get_referral_by_code(ref_from_start)
        if ref:
            await state.update_data(referral_code=ref_from_start)
            await cb.message.answer(at(lang, "ref_valid"))
        await show_summary_msg(cb.message, state, lang)
    else:
        await cb.message.answer(at(lang, "enter_ref"), reply_markup=kb_skip(lang))
        await state.set_state(AdminState.reg_ref)
 
 
@admin_router.message(AdminState.reg_ref)
async def reg_ref(msg: Message, state: FSMContext):
    lang = await get_lang(msg.from_user.id, state)
    skip = at(lang, "skip")
    if msg.text and skip not in msg.text:
        code = msg.text.strip().upper()
        ref = await get_referral_by_code(code)
        if ref:
            await state.update_data(referral_code=code)
            await msg.answer(at(lang, "ref_valid"))
        else:
            await msg.answer(at(lang, "ref_invalid"))
    await show_summary_msg(msg, state, lang)
 
 
async def show_summary_msg(msg: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    summary = build_summary(data)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=at(lang, "confirm_send"), callback_data="confirm_app"),
        InlineKeyboardButton(text=at(lang, "edit"),         callback_data="edit_app"),
    ]])
    await msg.answer(at(lang, "summary") + "\n\n" + summary,
                     reply_markup=kb)
    await state.set_state(AdminState.reg_confirm)
 
 
@admin_router.callback_query(F.data == "confirm_app", AdminState.reg_confirm)
async def confirm_app(cb: CallbackQuery, state: FSMContext):
    lang = await get_lang(cb.from_user.id, state)
    data = await state.get_data()
    await cb.message.edit_reply_markup()
    await cb.answer()
 
    promo_applied = False
    if data.get("promo_applied"):
        promo_applied = await use_promo_slot()
 
    plan_key  = data.get("plan", "start")
    plan_info = PLANS[plan_key]
    price     = plan_info["price_promo"] if promo_applied else plan_info["price"]
 
    app = await create_venue_application({
        "admin_telegram_id": cb.from_user.id,
        "lang":              lang,
        "bin":               data.get("bin", ""),
        "legal_name":        data.get("legal_name", ""),
        "okved":             data.get("okved", ""),
        "legal_address":     data.get("legal_address", ""),
        "brand_name":        data.get("brand_name", ""),
        "venue_type":        data.get("venue_type", "restaurant"),
        "actual_address":    data.get("actual_address", ""),
        "city":              data.get("city", "Алматы"),
        "phone":             data.get("phone", ""),
        "work_hours":        data.get("work_hours", ""),
        "avg_check":         data.get("avg_check", ""),
        "description":       data.get("description", ""),
        "video_url":         data.get("video_url"),
        "photos":            data.get("photos", []),
        "plan":              plan_key,
        "promo_applied":     promo_applied,
        "promo_price":       price,
        "referral_code":     data.get("referral_code"),
        "status":            "pending",
    })
 
    await state.clear()
    await cb.message.answer(at(lang, "app_sent"), reply_markup=ReplyKeyboardRemove())
 
    if app:
        await notify_owner(app, price)
 
 
@admin_router.callback_query(F.data == "edit_app")
async def edit_app(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_reply_markup()
    await cb.answer("Начните заново — /start")
 
 
async def notify_owner(app: dict, price: int):
    plan_info = PLANS.get(app.get("plan", "start"), PLANS["start"])
    promo_tag = " 🔥 АКЦИЯ -50%" if app.get("promo_applied") else ""
    slots_left = await get_promo_slots_left()
    text = (
        f"🆕 Новая заявка!\n\n"
        f"🏢 {app.get('brand_name','—')}\n"
        f"📂 {app.get('venue_type','—')}\n"
        f"📍 {app.get('city','—')}, {app.get('actual_address','—')}\n"
        f"📞 {app.get('phone','—')}\n"
        f"🔢 БИН: {app.get('bin','—')}\n"
        f"🏛 {app.get('legal_name','—')}\n"
        f"💳 {plan_info['name']} — {price} ₸/мес{promo_tag}\n"
        f"🔗 Реферал: {app.get('referral_code','—')}\n"
        f"👤 TG: {app.get('admin_telegram_id','—')}\n"
        f"🎯 Осталось акционных мест: {slots_left}"
    )
    try:
        await admin_bot.send_message(
            OWNER_ID, text,
            reply_markup=kb_approve_reject(app["id"])
        )
    except Exception as e:
        logger.error(f"notify_owner error: {e}")
 
 
# ══════════════════════════════════════════
# ОДОБРЕНИЕ / ОТКЛОНЕНИЕ (владелец)
# ══════════════════════════════════════════
 
@admin_router.callback_query(F.data.startswith("approv_"))
async def cb_approve(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Нет доступа", show_alert=True)
        return
    app_id = int(cb.data.split("_")[1])
    venue  = await approve_venue_application(app_id)
    app    = await get_venue_application(app_id)
    if not venue or not app:
        await cb.answer("Ошибка", show_alert=True)
        return
    await cb.message.edit_text(cb.message.text + "\n\n✅ ОДОБРЕНО")
    await cb.answer("Одобрено!")
 
    lang      = app.get("lang", "ru")
    plan_info = PLANS.get(app.get("plan", "start"), PLANS["start"])
    price     = app.get("promo_price") or plan_info["price"]
    pay_url   = generate_payment_url(
        amount=price,
        inv_id=app["id"],
        description=f"Reserva {plan_info['name']} — {app.get('brand_name','')}",
    )
 
    try:
        await admin_bot.send_message(app["admin_telegram_id"], at(lang, "approved"))
        if pay_url:
            await admin_bot.send_message(
                app["admin_telegram_id"],
                f"{plan_info['name']} — {price} ₸/мес",
                reply_markup=kb_pay(pay_url, lang)
            )
        else:
            await admin_bot.send_message(
                app["admin_telegram_id"],
                "Заведение активировано! 🎉",
                reply_markup=kb_main(lang, registered=True)
            )
    except Exception as e:
        logger.error(f"approve notify error: {e}")
 
 
@admin_router.callback_query(F.data.startswith("reject_"))
async def cb_reject(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Нет доступа", show_alert=True)
        return
    app_id = int(cb.data.split("_")[1])
    app    = await get_venue_application(app_id)
    if not app:
        await cb.answer("Не найдено", show_alert=True)
        return
    reason = "Данные не прошли проверку. Свяжитесь: @reserva_support"
    await reject_venue_application(app_id, reason)
    await cb.message.edit_text(cb.message.text + "\n\n❌ ОТКЛОНЕНО")
    await cb.answer("Отклонено")
    lang = app.get("lang", "ru")
    try:
        await admin_bot.send_message(app["admin_telegram_id"], at(lang, "rejected", reason))
    except Exception as e:
        logger.error(f"reject notify error: {e}")
 
 
@admin_router.callback_query(F.data == "pay_later")
async def cb_pay_later(cb: CallbackQuery):
    await cb.message.edit_reply_markup()
    await cb.answer("Хорошо, оплатите позже через /start")
 
 
# ══════════════════════════════════════════
# КАБИНЕТ ПАРТНЁРА
# ══════════════════════════════════════════
 
@admin_router.message(F.text.regexp(r"📝.*[Зз]арегистр|📝.*[Тт]іркеу|📝.*[Rr]egister"))
async def start_registration(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    lang = (user or {}).get("lang", "ru")
    await msg.answer(
        at(lang, "terms_prompt", TERMS_URL, PRIVACY_URL),
        parse_mode="HTML",
        reply_markup=kb_yes_no(at(lang, "terms_accept"), at(lang, "terms_decline"))
    )
    await state.update_data(lang=lang)
    await state.set_state(AdminState.terms)
 
 
@admin_router.message(F.text.regexp(r"🔔|Новые брони|Жаңа|New bookings"))
async def admin_new_bookings(msg: Message):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return
    bookings = await get_venue_bookings(venue["id"], pending_only=True)
    if not bookings:
        await msg.answer("Новых броней нет ✨")
        return
    for b in bookings:
        u = b.get("users") or {}
        text = (
            f"Бронь #{b['id']}\n"
            f"👤 {u.get('first_name','Гость')} · 📞 {b.get('phone','—')}\n"
            f"📅 {b.get('booking_date')}, {b.get('booking_time')}\n"
            f"👥 {b.get('guests_count')} гостей · {b.get('zone','—')}\n"
            f"📝 {b.get('wishes') or '—'}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅", callback_data=f"bk_ok_{b['id']}"),
            InlineKeyboardButton(text="❌", callback_data=f"bk_no_{b['id']}"),
        ]])
        await msg.answer(text, reply_markup=kb)
 
 
@admin_router.callback_query(F.data.startswith("bk_ok_"))
async def bk_confirm(cb: CallbackQuery):
    bid = int(cb.data.split("_")[2])
    await update_booking_status(bid, "confirmed")
    await cb.message.edit_text(cb.message.text + "\n\n✅ Подтверждено")
    await notify_user_confirmed(bid)
    await cb.answer("Подтверждено!")
 
 
@admin_router.callback_query(F.data.startswith("bk_no_"))
async def bk_decline(cb: CallbackQuery):
    bid = int(cb.data.split("_")[2])
    await update_booking_status(bid, "cancelled")
    await cb.message.edit_text(cb.message.text + "\n\n❌ Отклонено")
    await notify_user_cancelled(bid)
    await cb.answer("Отклонено")
 
 
@admin_router.message(F.text.regexp(r"🔄|Вкл/Выкл|қосу/өшіру|Toggle"))
async def toggle_bookings(msg: Message):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return
    new_val = not venue["is_available"]
    await update_venue(venue["id"], {"is_available": new_val})
    user = await get_user(msg.from_user.id)
    lang = (user or {}).get("lang", "ru")
    status = "включён ✅" if new_val else "остановлен ⏸️"
    await msg.answer(f"Приём броней {status}", reply_markup=kb_main(lang, registered=True))
 
 
@admin_router.message(F.text.regexp(r"📊|Статистика|Statistics"))
async def admin_stats(msg: Message):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return
    all_bk = await get_venue_bookings(venue["id"], pending_only=False)
    await msg.answer(
        f"📊 {venue['name']}\n\n"
        f"Всего броней: {len(all_bk)}\n"
        f"✅ Подтверждено: {sum(1 for b in all_bk if b['status']=='confirmed')}\n"
        f"⏳ Ожидает: {sum(1 for b in all_bk if b['status']=='pending')}\n"
        f"❌ Отменено: {sum(1 for b in all_bk if b['status']=='cancelled')}"
    )
 
 
@admin_router.message(F.text.regexp(r"🎁|Рефераль|Рефералд|Referral"))
async def admin_referral(msg: Message):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        await msg.answer("Реферальная программа доступна после регистрации.")
        return
    user = await get_user(msg.from_user.id)
    lang = (user or {}).get("lang", "ru")
    code  = await get_or_create_referral_code(msg.from_user.id)
    stats = await get_referral_stats(msg.from_user.id)
    await msg.answer(at(lang, "ref_code", code, stats["referrals_count"], stats["bonus_months"]))
 
 
@admin_router.message(F.text.regexp(r"⚙️|Язык|Тіл|Language"))
async def change_lang_start(msg: Message, state: FSMContext):
    await msg.answer("Выберите язык · Тілді таңдаңыз · Choose language:", reply_markup=kb_lang())
    await state.set_state(AdminState.change_lang)
 
 
@admin_router.message(AdminState.change_lang)
async def change_lang_done(msg: Message, state: FSMContext):
    code = ADMIN_LANGS.get(msg.text)
    if not code:
        await msg.answer("Выберите из списка:", reply_markup=kb_lang())
        return
    await set_user_lang(msg.from_user.id, code)
    await state.clear()
    venue = await get_venue_admin(msg.from_user.id)
    await msg.answer(at(code, "lang_saved"), reply_markup=kb_main(code, registered=bool(venue)))
 
 
# ══════════════════════════════════════════
# МЕНЮ
# ══════════════════════════════════════════
 
@admin_router.message(F.text.regexp(r"🍽️.*[Мм]ен|🍽️.*[Мм]әзір|🍽️.*[Mm]enu"))
async def menu_main(msg: Message):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return
    cats = await get_menu_categories(venue["id"])
    if not cats:
        text = "Меню пустое. Добавьте первую категорию."
    else:
        lines = [f"Меню · {venue['name']}\n"]
        for cat in cats:
            items = await get_menu_items(venue["id"], cat["id"])
            lines.append(f"📂 {cat['name']} — {len(items)} блюд")
        text = "\n".join(lines)
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Категория"), KeyboardButton(text="➕ Блюдо")],
        [KeyboardButton(text="📋 Список блюд")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True)
    await msg.answer(text, reply_markup=kb)
 
 
@admin_router.message(F.text == "➕ Категория")
async def add_cat_start(msg: Message, state: FSMContext):
    await msg.answer("Введите название категории (Горячее, Птица, Мясо, Напитки…):")
    await state.set_state(AdminState.menu_add_cat_name)
 
 
@admin_router.message(AdminState.menu_add_cat_name)
async def add_cat_save(msg: Message, state: FSMContext):
    venue = await get_venue_admin(msg.from_user.id)
    if venue:
        await create_menu_category(venue["id"], msg.text.strip())
    await state.clear()
    await msg.answer(f"Категория «{msg.text.strip()}» создана ✅")
    await menu_main(msg)
 
 
@admin_router.message(F.text == "📋 Список блюд")
async def list_dishes(msg: Message):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return
    cats = await get_menu_categories(venue["id"])
    for cat in cats:
        items = await get_menu_items(venue["id"], cat["id"])
        if not items:
            await msg.answer(f"📂 {cat['name']} — пусто")
            continue
        lines = [f"📂 {cat['name']}:"]
        for it in items:
            s = "✅" if it["is_available"] else "⏸"
            lines.append(f"{s} {it['name']} — {it['price']:,} ₸  /dish_{it['id']}".replace(",", " "))
        await msg.answer("\n".join(lines))
 
 
@admin_router.message(F.text.regexp(r'^/dish_\d+$'))
async def dish_control(msg: Message):
    item_id = int(msg.text.split("_")[1])
    item = await get_menu_item(item_id)
    if not item:
        await msg.answer("Не найдено.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="⏸ Стоп" if item["is_available"] else "▶️ Вкл",
            callback_data=f"dtoggle_{item_id}"
        ),
        InlineKeyboardButton(text="🗑", callback_data=f"ddel_{item_id}")
    ]])
    price_fmt = f"{item['price']:,}".replace(",", " ")
    await msg.answer(
        f"{item['name']} — {price_fmt} ₸\n{'✅' if item['is_available'] else '⏸'}",
        reply_markup=kb
    )
 
 
@admin_router.callback_query(F.data.startswith("dtoggle_"))
async def dish_toggle(cb: CallbackQuery):
    item_id = int(cb.data.split("_")[1])
    new_val = await toggle_item_availability(item_id)
    await cb.message.edit_text(cb.message.text + f"\n→ {'✅' if new_val else '⏸'}")
    await cb.answer()
 
 
@admin_router.callback_query(F.data.startswith("ddel_"))
async def dish_del(cb: CallbackQuery):
    item_id = int(cb.data.split("_")[1])
    await delete_menu_item(item_id)
    await cb.message.edit_text(cb.message.text + "\n🗑 Удалено")
    await cb.answer("Удалено")
 
 
@admin_router.message(F.text == "➕ Блюдо")
async def add_dish_start(msg: Message, state: FSMContext):
    venue = await get_venue_admin(msg.from_user.id)
    if not venue:
        return
    cats = await get_menu_categories(venue["id"])
    if not cats:
        await msg.answer("Сначала создайте категорию.")
        return
    lines = ["Выберите категорию:\n"]
    for cat in cats:
        lines.append(f"/cat_{cat['id']}  {cat['name']}")
    await msg.answer("\n".join(lines))
    await state.set_state(AdminState.menu_add_dish_cat)
    await state.update_data(venue_id=venue["id"])
 
 
@admin_router.message(F.text.regexp(r'^/cat_\d+$'), AdminState.menu_add_dish_cat)
async def add_dish_cat(msg: Message, state: FSMContext):
    await state.update_data(category_id=int(msg.text.split("_")[1]))
    await msg.answer("Название блюда:")
    await state.set_state(AdminState.menu_add_dish_name)
 
 
@admin_router.message(AdminState.menu_add_dish_name)
async def add_dish_name(msg: Message, state: FSMContext):
    await state.update_data(dish_name=msg.text.strip())
    await msg.answer("Цена в тенге (например: 2500):")
    await state.set_state(AdminState.menu_add_dish_price)
 
 
@admin_router.message(AdminState.menu_add_dish_price)
async def add_dish_price(msg: Message, state: FSMContext):
    try:
        price = int(msg.text.strip().replace(" ", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await msg.answer("Введите корректную цену:")
        return
    await state.update_data(dish_price=price)
    await msg.answer("Состав/описание (или — чтобы пропустить):")
    await state.set_state(AdminState.menu_add_dish_desc)
 
 
@admin_router.message(AdminState.menu_add_dish_desc)
async def add_dish_desc(msg: Message, state: FSMContext):
    d = await state.get_data()
    await state.clear()
    item = await create_menu_item({
        "venue_id":    d["venue_id"],
        "category_id": d["category_id"],
        "name":        d["dish_name"],
        "price":       d["dish_price"],
        "description": "" if msg.text.strip() == "—" else msg.text.strip(),
        "media_type":  "jpg",
        "is_hit":      False,
        "is_new":      False,
    })
    if item:
        await msg.answer(f"Блюдо добавлено ✅ — /dish_{item['id']}")
    else:
        await msg.answer("Ошибка. Попробуйте снова.")
 
 
@admin_router.message(F.text == "🔙 Назад")
async def go_back(msg: Message, state: FSMContext):
    await state.clear()
    user = await get_user(msg.from_user.id)
    lang = (user or {}).get("lang", "ru")
    venue = await get_venue_admin(msg.from_user.id)
    await msg.answer("Главное меню", reply_markup=kb_main(lang, registered=bool(venue)))
 
 
# ══════════════════════════════════════════
# УВЕДОМЛЕНИЯ КЛИЕНТАМ
# ══════════════════════════════════════════
 
async def notify_venue_new_booking(booking_data: dict):
    venue = await get_venue(booking_data.get("venueId"))
    if not venue or not venue.get("admin_telegram_id"):
        return
    try:
        bookings = await get_venue_bookings(venue["id"], pending_only=True)
        bid = bookings[0]["id"] if bookings else 0
        text = (
            f"🔔 Новая бронь!\n\n"
            f"👤 {booking_data.get('name','Гость')} · 📞 {booking_data.get('phone','—')}\n"
            f"📅 {booking_data.get('date')}, {booking_data.get('time')}\n"
            f"👥 {booking_data.get('guests')} гостей · {booking_data.get('zone','—')}\n"
            f"📝 {booking_data.get('wishes') or '—'}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅", callback_data=f"bk_ok_{bid}"),
            InlineKeyboardButton(text="❌", callback_data=f"bk_no_{bid}"),
        ]])
        await admin_bot.send_message(venue["admin_telegram_id"], text, reply_markup=kb)
    except Exception as e:
        logger.error(f"notify_venue error: {e}")
 
 
async def notify_user_confirmed(booking_id: int):
    try:
        from database import supabase
        from bot import bot
        b = supabase.table("bookings").select("*, venues(name,emoji)").eq("id", booking_id).single().execute().data
        if not b:
            return
        v = b.get("venues") or {}
        await bot.send_message(
            b["user_telegram_id"],
            f"✅ Бронь подтверждена!\n\n{v.get('emoji','')} {v.get('name','')}\n"
            f"📅 {b['booking_date']}, {b['booking_time']}\n"
            f"👥 {b['guests_count']} гостей\n\nЖдём вас! 😊"
        )
    except Exception as e:
        logger.error(f"notify_confirmed error: {e}")
 
 
async def notify_user_cancelled(booking_id: int):
    try:
        from database import supabase
        from bot import bot
        b = supabase.table("bookings").select("*, venues(name)").eq("id", booking_id).single().execute().data
        if not b:
            return
        v = b.get("venues") or {}
        await bot.send_message(
            b["user_telegram_id"],
            f"К сожалению, {v.get('name','')} не смогло принять вашу бронь.\n"
            f"Попробуйте другое время — /start"
        )
    except Exception as e:
        logger.error(f"notify_cancelled error: {e}")
 
