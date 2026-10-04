#!/usr/bin/env bash
# Установка Telegram-бота «Лёгкая еда» на Ubuntu/Debian VPS.
# Запускать от root:  sudo bash deploy.sh
set -euo pipefail

REPO="https://github.com/fatalerrorcard/easy-food-bot.git"
APP_DIR="/opt/easy-food-bot"
SERVICE="/etc/systemd/system/easy-food-bot.service"
ENV_FILE="$APP_DIR/.env"

echo "==> 1. Обновляем систему и ставим зависимости"
apt-get update -y
apt-get install -y git python3 python3-venv python3-pip

echo "==> 2. Клонируем бота"
if [ -d "$APP_DIR" ]; then
    cd "$APP_DIR" && git pull origin main
else
    git clone "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

echo "==> 3. Создаём виртуальное окружение и ставим пакеты"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "==> 4. Настраиваем .env с токеном"
if [ ! -f "$ENV_FILE" ]; then
    cp "$APP_DIR/.env.example" "$ENV_FILE"
    echo "Создан $ENV_FILE. Впишите в него токен!"
fi

# Проверяем, что токен реально вписан (ВНИМАНИЕ: не выводим сам токен!)
TOKEN_SET=0
if [ -f "$ENV_FILE" ] && grep -qE '^BOT_TOKEN=[^ ]+$' "$ENV_FILE"; then
    TOKEN_SET=1
fi

echo "==> 5. Кладём unit-файл systemd"
cp "$APP_DIR/deploy/easy-food-bot.service" "$SERVICE"

echo "==> 6. Права на папку (сервис запускается от root/деплойера)"
chmod +x "$APP_DIR/venv/bin/python"
chmod 600 "$ENV_FILE"

echo "==> 7. Включаем и запускаем сервис"
systemctl daemon-reload
systemctl enable easy-food-bot

if [ "$TOKEN_SET" = "1" ]; then
    systemctl restart easy-food-bot
    echo ""
    echo "=============================================="
    echo "Готово! Статус:"
    echo "  systemctl status easy-food-bot"
    echo "Логи:"
    echo "  journalctl -u easy-food-bot -f"
    echo "=============================================="
else
    echo ""
    echo "=============================================="
    echo "ВНИМАНИЕ: токен НЕ вписан в $ENV_FILE!"
    echo "Сделайте сейчас:"
    echo "  nano $ENV_FILE"
    echo "  (впишите BOT_TOKEN=ваш_токен от @BotFather)"
    echo "Затем запустите:"
    echo "  systemctl restart easy-food-bot"
    echo "  systemctl status easy-food-bot"
    echo "=============================================="
fi