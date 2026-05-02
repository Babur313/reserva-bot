import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from aiogram.types import Update

from config import BOT_TOKEN, ADMIN_BOT_TOKEN, WEBHOOK_BASE
from bot import bot, dp
from admin_bot import admin_bot, admin_dp
from menu_router import menu_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

WEBHOOK_PATH       = f"/webhook/{BOT_TOKEN}"
ADMIN_WEBHOOK_PATH = f"/webhook/admin/{ADMIN_BOT_TOKEN}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Старт
    await bot.set_webhook(
        url=f"{WEBHOOK_BASE}{WEBHOOK_PATH}",
        allowed_updates=["message", "callback_query", "web_app_data"]
    )
    await admin_bot.set_webhook(
        url=f"{WEBHOOK_BASE}{ADMIN_WEBHOOK_PATH}",
        allowed_updates=["message", "callback_query"]
    )
    logger.info("Webhooks registered")
    yield
    # Стоп
    await bot.delete_webhook()
    await admin_bot.delete_webhook()
    await bot.session.close()
    await admin_bot.session.close()
    logger.info("Webhooks removed, sessions closed")


app = FastAPI(title="Reserva API", lifespan=lifespan)
app.include_router(menu_router)


@app.post(WEBHOOK_PATH)
async def client_webhook(request: Request):
    try:
        body = await request.json()
        update = Update.model_validate(body, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.error(f"Client webhook error: {e}")
    return Response(content="ok")


@app.post(ADMIN_WEBHOOK_PATH)
async def admin_webhook(request: Request):
    try:
        body = await request.json()
        update = Update.model_validate(body, context={"bot": admin_bot})
        await admin_dp.feed_update(admin_bot, update)
    except Exception as e:
        logger.error(f"Admin webhook error: {e}")
    return Response(content="ok")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Reserva"}
