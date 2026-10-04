# -*- coding: utf-8 -*-
"""
Telegram-бот «Лёгкая еда».
Пользователь диктует продукты — бот подсказывает, что из них можно
быстро и просто приготовить.

Запуск:  python -m easy_bot.bot
(предварительно положите токен в переменную окружения BOT_TOKEN
или в файл .env рядом с проектом)
"""
import asyncio
import json
import logging
import os
import sys

# Кладём корень проекта в sys.path, чтобы бот работал из любой папки
# (и при двойном клике по файлу, и из командной строки).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

# Файл со списком подписчиков (всех, кому нужно слать уведомления о запуске)
_SUBSCRIBERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscribers.json")


def _load_subscribers() -> list:
    """Читает список подписчиков (chat_id) из файла."""
    try:
        if os.path.exists(_SUBSCRIBERS_FILE):
            with open(_SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [int(x) for x in data if isinstance(x, (int, str)) and str(x).lstrip("-").isdigit()]
        return []
    except Exception:
        return []


def _save_subscribers(chat_ids: list) -> None:
    """Сохраняет список подписчиков в файл."""
    try:
        with open(_SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(set(chat_ids)), f, ensure_ascii=False)
    except Exception as e:
        log.warning("Не удалось сохранить список подписчиков: %s", e)


def _add_subscriber(chat_id) -> None:
    """Добавляет chat_id в список подписчиков."""
    subscribers = _load_subscribers()
    if chat_id not in subscribers:
        subscribers.append(chat_id)
        _save_subscribers(subscribers)

try:
    from dotenv import load_dotenv

    # .env лежит рядом с bot.py
    _ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_ENV_PATH)
    load_dotenv()  # дополнительно пробуем из текущей папки
except ImportError:  # python-dotenv не установлен — просто читаем окружение
    pass

try:
    # Запуск как пакет: python -m easy_bot.bot
    from easy_bot import matcher
except ImportError:
    # Плоская структура на сервере: python bot.py
    import matcher

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

HELP_TEXT = (
    "Я бот для лёгкой еды 🥪\n\n"
    "Просто напиши, какие продукты у тебя есть — "
    "например:\n\n"
    "   сыр, колбаса, хлеб\n"
    "   яйца и помидоры\n"
    "   творог банан мёд\n\n"
    "Я подскажу, что из этого можно быстро приготовить: "
    "бутерброды, закуски, сытные блюда и вкусняшки.\n\n"
    "Команды:\n"
    "/start — приветствие\n"
    "/help — эта справка\n"
    "/random — случайный рецепт из базы\n"
    "/subscribe — получать уведомление, когда я запускаюсь\n"
    "/unsubscribe — отписаться от уведомлений"
)

# Простая клавиатура с часто встречающимися продуктами
COMMON_PRODUCTS = [
    ["хлеб", "сыр", "колбаса"],
    ["яйца", "помидор", "огурец"],
    ["творог", "банан", "мёд"],
]
reply_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=p) for p in row] for row in COMMON_PRODUCTS],
    resize_keyboard=True,
)

bot = None
dp = Dispatcher()


# Рассылает уведомление о запуске всем подписчикам после успешного старта поллинга.
@dp.startup()
async def on_startup() -> None:
    if bot is None:
        return
    try:
        await notify_subscribers(bot)
    except Exception as e:
        log.error("Ошибка рассылки о запуске: %s", e, exc_info=True)


@dp.message(CommandStart())
async def cmd_start(message: Message):
    _add_subscriber(message.chat.id)
    await message.answer(
        "Привет! Я помогу приготовить еду из того, что есть под рукой. 😋\n"
        "Напиши свои продукты — и я подскажу, что можно сделать.\n\n"
        "Чтобы получать уведомления, когда я перезапускаюсь, "
        "нажмите /subscribe. Рассылка идёт всем, кто пользовался ботом.",
        reply_markup=reply_kb,
    )


@dp.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    subscribers = _load_subscribers()
    if message.chat.id in subscribers:
        await message.answer("Вы уже подписаны на уведомления. ✅")
    else:
        _add_subscriber(message.chat.id)
        await message.answer("Готово! Теперь я пришлю вам сообщение, когда снова запущусь. ✅")


@dp.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message):
    subscribers = _load_subscribers()
    if message.chat.id in subscribers:
        subscribers = [x for x in subscribers if x != message.chat.id]
        _save_subscribers(subscribers)
        await message.answer("Вы отписаны от уведомлений. 👋")
    else:
        await message.answer("Вы и так не подписаны.")


@dp.message(Command("help"))
async def cmd_help(message: Message):
    _add_subscriber(message.chat.id)
    await message.answer(HELP_TEXT, reply_markup=reply_kb)


@dp.message(Command("random"))
async def cmd_random(message: Message):
    _add_subscriber(message.chat.id)
    import random

    rec = random.choice(matcher._RECIPE_NORMS)["orig"]
    await message.answer(
        matcher.describe_match(rec, 0, 0),
        reply_markup=reply_kb,
    )


@dp.message(F.text)
async def on_text(message: Message):
    _add_subscriber(message.chat.id)
    text = message.text.strip()
    normalized = matcher.normalize_text(text)
    if not normalized:
        await message.answer(
            "Я тебя не понял 🤔 Напиши продукты через запятую, например: «хлеб, сыр, яйца».",
            reply_markup=reply_kb,
        )
        return

    results = matcher.recommend(text, top=4)
    if not results:
        await message.answer(
            "Пока не нашёл блюд по этим продуктам. 🤷 "
            "Попробуй добавить ещё пару продуктов или напиши их по-другому.\n"
            "Например: хлеб, сыр, колбаса, яйца, помидоры.",
            reply_markup=reply_kb,
        )
        return

    await message.answer(
        f"Вот что можно приготовить из: *{text}* 🍳\n\n"
        + "\n\n".join(matcher.describe_match(rec, cnt, frac) for rec, cnt, frac in results),
        parse_mode="Markdown",
        reply_markup=reply_kb,
    )


async def notify_subscribers(bot: Bot):
    """Рассылает всем подписчикам сообщение о том, что бот запущен."""
    subscribers = _load_subscribers()
    if not subscribers:
        log.info("Нет подписчиков для уведомления о запуске.")
        return
    text = "🔔 Я снова в сети! Могу подсказать, что приготовить. Просто напишите продукты."
    sent = 0
    for chat_id in subscribers:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            sent += 1
            await asyncio.sleep(0.05)  # не спускать ограничение скорости Telegram
        except Exception as e:
            # Случай, когда пользователь заблокировал бота или чат недоступен
            log.warning("Не удалось отправить уведомление %s: %s", chat_id, e)
    log.info("Рассылка о запуске: отправлено %d из %d подписчиков.", sent, len(subscribers))


async def main():
    global bot
    if not BOT_TOKEN:
        raise SystemExit(
            "Не задан токен. Положите его в переменную окружения BOT_TOKEN "
            "или создайте файл .env рядом с проектом с строкой:\nBOT_TOKEN=ваш_токен"
        )
    bot = Bot(token=BOT_TOKEN)
    log.info("Бот запущен (поллинг). Нажмите Ctrl+C для остановки.")
    try:
        # Запускаем поллинг. Если он упадёт - перехватим и залогируем,
        # чтобы systemd мог перезапустить бота, а не оставлять его "мёртвым".
        try:
            await dp.start_polling(bot)
        except Exception as e:
            log.error("Ошибка поллинга: %s", e, exc_info=True)
            raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())