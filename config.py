import os
from dotenv import load_dotenv
load_dotenv()
 
BOT_TOKEN        = os.getenv("BOT_TOKEN")
ADMIN_BOT_TOKEN  = os.getenv("ADMIN_BOT_TOKEN")
ANTHROPIC_KEY    = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL     = os.getenv("SUPABASE_URL")
SUPABASE_KEY     = os.getenv("SUPABASE_KEY")
WEBHOOK_BASE     = os.getenv("WEBHOOK_BASE_URL")
MINIAPP_URL      = os.getenv("MINIAPP_URL", "https://reserva-miniapp.vercel.app")
 
# Владелец системы — получает уведомления о новых партнёрах
OWNER_ID         = int(os.getenv("OWNER_TELEGRAM_ID", "1584193272"))
 
# Robokassa
ROBOKASSA_LOGIN  = os.getenv("ROBOKASSA_LOGIN", "")
ROBOKASSA_PASS1  = os.getenv("ROBOKASSA_PASS1", "")
ROBOKASSA_PASS2  = os.getenv("ROBOKASSA_PASS2", "")
ROBOKASSA_TEST   = os.getenv("ROBOKASSA_TEST", "1")  # 1=тест, 0=боевой
 
# Тарифы
PLANS = {
    "start":    {"name": "Старт",   "price": 4900,  "price_promo": 2450},
    "business": {"name": "Бизнес",  "price": 7900,  "price_promo": 3950},
    "pro":      {"name": "Про",     "price": 9900,  "price_promo": 4950},
}
 
# Промо-акция
PROMO_TOTAL    = 50    # всего мест
PROMO_DISCOUNT = 50   # скидка в %
PROMO_MONTHS   = 3    # месяцев по акции
 
# Ссылки на документы
TERMS_URL      = "https://reserva-miniapp.vercel.app/terms"
PRIVACY_URL    = "https://reserva-miniapp.vercel.app/privacy"
 
