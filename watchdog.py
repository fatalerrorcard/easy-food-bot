# -*- coding: utf-8 -*-
"""
Watchdog (супервизор) для Telegram-бота «Лёгкая еда».

Запускает bot.py как дочерний процесс и держит его живым:
- если бот упал (аварийно завершился) — перезапускает через 3 секунды;
- если бот завис (не отвечает более timeout_healthcheck_sec) — убивает и перезапускает;
- пишет лог в logs/watchdog.log.

Запуск:  python easy_bot\watchdog.py
"""
import datetime
import logging
import os
import signal
import subprocess
import sys
import threading
import time

# Корень проекта
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_SCRIPT = os.path.join(PROJECT_ROOT, "easy_bot", "bot.py")

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "watchdog.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("watchdog")

# Параметры
RESTART_DELAY_SEC = 3          # пауза перед перезапуском после падения
HEALTHCHECK_SEC = 180          # если бот не пишет в stdout дольше этого — считаем зависшим
MAX_CONSECUTIVE_FAILS = 20     # защита: если столько раз подряд падает за 60 сек — выходим


class BotController:
    """Запускает бота, следит за его жизнью и перезапускает."""

    def __init__(self):
        self.proc = None
        self.last_output_ts = [time.time()]
        self.heartbeat = threading.Event()

    def _spawn(self):
        log.info("Запускаю бота: %s", BOT_SCRIPT)
        self.proc = subprocess.Popen(
            [sys.executable, "-u", BOT_SCRIPT],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.last_output_ts[0] = time.time()
        # фоновая задача: обновляем время последнего живого вывода
        self._monitor_out(self.proc)
        return self.proc

    def _monitor_out(self, proc):
        def reader():
            try:
                for line in proc.stdout:
                    line = line.rstrip()
                    if line:
                        self.last_output_ts[0] = time.time()
                        log.info("BOT| %s", line)
            except Exception:
                pass
        t = threading.Thread(target=reader, daemon=True)
        t.start()

    def run_forever(self):
        restart_count = 0
        fails_window = []  # времена последних аварийных остановок
        while True:
            proc = self._spawn()
            # ждём завершения процесса или перезапускаем по зависанию
            while True:
                time.sleep(2)
                rc = proc.poll()
                if rc is not None:
                    # процесс завершился
                    log.warning("Бот завершился с кодом %s", rc)
                    restart_count += 1
                    fails_window.append(time.time())
                    break
                # проверка на зависание
                now = time.time()
                if now - self.last_output_ts[0] > HEALTHCHECK_SEC:
                    log.warning(
                        "Бот не подаёт признаков жизни %s сек, принудительно перезапускаю",
                        HEALTHCHECK_SEC,
                    )
                    proc.kill()
                    restart_count += 1
                    fails_window.append(time.time())
                    break
            # защита от бесконечного цикла паданий
            fails_window = [t for t in fails_window if time.time() - t < 60]
            if len(fails_window) >= MAX_CONSECUTIVE_FAILS:
                log.error(
                    "Бот упал %d раз за минуту — останавливаю watchdog, проверьте логи.",
                    len(fails_window),
                )
                return
            time.sleep(RESTART_DELAY_SEC)


def main():
    log.info("=" * 60)
    log.info("Watchdog запущен.")
    log.info("Лог: %s", LOG_FILE)
    if not os.path.exists(BOT_SCRIPT):
        log.error("Не найден файл бота: %s — выходим.", BOT_SCRIPT)
        sys.exit(1)
    ctl = BotController()
    try:
        ctl.run_forever()
    except KeyboardInterrupt:
        log.info("Watchdog остановлен по Ctrl+C.")
    finally:
        if ctl.proc and ctl.proc.poll() is None:
            log.info("Останавливаю бота...")
            ctl.proc.terminate()


if __name__ == "__main__":
    main()