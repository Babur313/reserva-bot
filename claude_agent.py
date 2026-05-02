"""
claude_agent.py — ИИ-агент на Claude Sonnet.
Поддерживает языки: ru (русский), kz (қазақша), en (english).
Отвечает строго на языке пользователя.
Фильтрует заведения по городу.
"""

import anthropic
import json
from config import ANTHROPIC_KEY
from database import get_venues

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# ── Системный промпт (кэшируется — экономит токены) ──────

SYSTEM_BASE = """Ты — вежливый ИИ-ассистент сервиса Reserva для бронирования столиков.

ГЛАВНОЕ ПРАВИЛО: ты ВСЕГДА отвечаешь ТОЛЬКО на том языке, который указан в параметре ЯЗЫК ОТВЕТА.
Если указан "kz" — отвечай только по-казахски.
Если указан "en" — отвечай только по-английски.
Если указан "ru" — отвечай только по-русски.
Никогда не смешивай языки в одном ответе.

ЗАДАЧА — за 3–4 вопроса узнать:
1. Тип заведения (restaurant / cafe / hookah / karaoke)
2. Количество гостей (число)
3. Дату (today / tomorrow / weekend / other)
4. Примерное время (строка HH:00)

После сбора параметров — показать заведения из контекста и предложить мини-приложение.

ПРАВИЛА ДИАЛОГА:
- Кратко — максимум 2–3 предложения за ответ
- Веди живой диалог, не спрашивай всё сразу
- Если пользователь пишет "помогите выбрать" — уточни повод
- Используй только заведения из переданного контекста, не придумывай
- Если свободных мест нет — честно скажи и предложи альтернативу

ФОРМАТ ОТВЕТА — строго валидный JSON без текста снаружи:
{
  "message": "текст для пользователя",
  "quick_replies": ["вариант1", "вариант2"],
  "show_venues": false,
  "ready_to_book": false,
  "collected": {
    "type": null,
    "guests": null,
    "date": null,
    "time": null
  }
}

quick_replies — 2–4 варианта на языке пользователя, или [] если не нужны.
show_venues = true когда нужно показать список заведений.
ready_to_book = true когда все 4 параметра собраны."""

# Подсказки quick_replies на каждом языке
QUICK_HINTS = {
    "ru": {
        "types":    ["🍽️ Ресторан", "☕ Кафе", "💨 Кальянная", "🎤 Каракое"],
        "occasion": ["💼 Деловая встреча", "💑 Романтический ужин", "🎂 День рождения", "👫 С друзьями"],
        "guests":   ["1", "2", "3–4", "5+"],
        "dates":    ["Сегодня", "Завтра", "На выходных", "Другой день"],
        "times":    ["12:00", "15:00", "18:00", "19:00", "21:00"],
    },
    "kz": {
        "types":    ["🍽️ Мейрамхана", "☕ Кафе", "💨 Кальян", "🎤 Кара-оке"],
        "occasion": ["💼 Іскери кездесу", "💑 Романтикалық кеш", "🎂 Туған күн", "👫 Достармен"],
        "guests":   ["1", "2", "3–4", "5+"],
        "dates":    ["Бүгін", "Ертең", "Демалыс күні", "Басқа күн"],
        "times":    ["12:00", "15:00", "18:00", "19:00", "21:00"],
    },
    "en": {
        "types":    ["🍽️ Restaurant", "☕ Café", "💨 Hookah lounge", "🎤 Karaoke"],
        "occasion": ["💼 Business meeting", "💑 Romantic dinner", "🎂 Birthday", "👫 Friends"],
        "guests":   ["1", "2", "3–4", "5+"],
        "dates":    ["Today", "Tomorrow", "This weekend", "Another day"],
        "times":    ["12:00", "15:00", "18:00", "19:00", "21:00"],
    },
}


async def chat_with_claude(
    conversation_history: list,
    user_message: str,
    collected_params: dict,
    venues_context: str,
    lang: str = "ru",
    city: str = "Алматы",
) -> dict:
    """
    Отправляет сообщение в Claude Sonnet и возвращает структурированный ответ.
    lang: "ru" | "kz" | "en"
    city: название города для контекста
    """
    if lang not in ("ru", "kz", "en"):
        lang = "ru"

    hints = QUICK_HINTS[lang]

    # Динамическая часть (меняется каждый запрос, не кэшируется)
    dynamic = f"""
ЯЗЫК ОТВЕТА: {lang}
ГОРОД: {city}

ПРИМЕРЫ QUICK_REPLIES для этого языка:
- Типы заведений: {hints["types"]}
- Повод: {hints["occasion"]}
- Гости: {hints["guests"]}
- Дата: {hints["dates"]}
- Время: {hints["times"]}

ЗАВЕДЕНИЯ В {city.upper()}:
{venues_context}

УЖЕ СОБРАНО:
{json.dumps(collected_params, ensure_ascii=False, indent=2)}

Отвечай ТОЛЬКО валидным JSON без какого-либо текста снаружи.
"""

    history = conversation_history.copy()
    history.append({"role": "user", "content": user_message})

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_BASE,
                    "cache_control": {"type": "ephemeral"}  # кэш ~5 минут
                },
                {
                    "type": "text",
                    "text": dynamic
                }
            ],
            messages=history
        )

        raw = response.content[0].text.strip()

        # Очищаем от возможных markdown-обёрток
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        result.setdefault("message", "")
        result.setdefault("quick_replies", [])
        result.setdefault("show_venues", False)
        result.setdefault("ready_to_book", False)
        result.setdefault("collected", collected_params)
        return result

    except json.JSONDecodeError:
        # Fallback на языке пользователя
        fallback = {
            "ru": "Давайте начнём заново. Какой тип заведения вас интересует?",
            "kz": "Қайтадан бастайық. Қандай мекеме қызықтырады?",
            "en": "Let's start over. What type of venue are you looking for?",
        }
        return {
            "message":       fallback.get(lang, fallback["ru"]),
            "quick_replies": hints["types"],
            "show_venues":   False,
            "ready_to_book": False,
            "collected":     collected_params,
        }

    except anthropic.APIError as e:
        error_msg = {
            "ru": "Сервис временно недоступен, попробуйте через минуту 🙏",
            "kz": "Қызмет уақытша қолжетімсіз, бір минуттан кейін қайталаңыз 🙏",
            "en": "Service is temporarily unavailable, please try again in a minute 🙏",
        }
        return {
            "message":       error_msg.get(lang, error_msg["ru"]),
            "quick_replies": [],
            "show_venues":   False,
            "ready_to_book": False,
            "collected":     collected_params,
        }


async def build_venues_context(type_filter: str = None, city: str = "Алматы") -> str:
    """
    Формирует текстовый контекст о заведениях для промпта.
    Фильтрует по типу и городу.
    """
    # Нормализуем тип из любого языка
    type_map = {
        # ru
        "ресторан": "restaurant", "кафе": "cafe",
        "кальянная": "hookah", "каракое": "karaoke",
        # kz
        "мейрамхана": "restaurant", "кальян": "hookah", "кара-оке": "karaoke",
        # en
        "restaurant": "restaurant", "café": "cafe", "cafe": "cafe",
        "hookah lounge": "hookah", "hookah": "hookah", "karaoke": "karaoke",
        # emoji-варианты
        "🍽️ ресторан": "restaurant", "☕ кафе": "cafe",
        "💨 кальянная": "hookah", "🎤 каракое": "karaoke",
    }
    if type_filter:
        type_filter = type_map.get(type_filter.lower().strip(), type_filter)

    venues = await get_venues(type_filter)

    if not venues:
        return f"Заведений в {city} по данному критерию не найдено."

    lines = []
    for v in venues:
        avail = "✅ есть места" if v.get("is_available") else "❌ занято"
        tags  = ", ".join(v.get("tags", [])[:3]) if v.get("tags") else "—"
        lines.append(
            f"ID:{v['id']} | {v.get('emoji','')} {v['name']} [{v.get('type_label', v['type'])}]\n"
            f"  Адрес: {v.get('address', '')}\n"
            f"  Чек: {v.get('avg_check', '')} | Рейтинг: {v.get('rating', '')} | {avail}\n"
            f"  Особенности: {tags}"
        )

    return "\n\n".join(lines)
