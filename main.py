# -*- coding: utf-8 -*-
"""
Точка входа для хостингов, которые запускают бота командой:
    python main.py

(стандарт для Bothost и многих PaaS-платформ).
Просто запускает то же самое, что и bot.py.
"""
import asyncio

from bot import main

if __name__ == "__main__":
    asyncio.run(main())