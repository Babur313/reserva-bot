import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN       = os.getenv("BOT_TOKEN")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
WEBHOOK_BASE    = os.getenv("WEBHOOK_BASE_URL")
MINIAPP_URL     = os.getenv("MINIAPP_URL", "https://your-app.vercel.app")
