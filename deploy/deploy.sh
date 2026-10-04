#!/usr/bin/env bash
# Установка Telegram-бота «Лёгкая еда» на Ubuntu/Debian VPS.
# Запускать от root:  sudo bash deploy.sh
set -euo pipefail

REPO="https://github.com/fatalerrorcard/easy-food-bot.git"
APP_DIR="/opt/easy-food-bot"
SERVICE="/etc/systemd/system/easy-food-bot.service"

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
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo "ВНИМАНИЕ: откройте $APP_DIR/.env и впишите BOT_TOKEN=ваш_токен"
    echo "Затем перезапустите: systemctl restart easy-food-bot"
fi

echo "==> 5. Кладём unit-файл systemd"
cp "$APP_DIR/deploy/easy-food-bot.service" "$SERVICE"

echo "==> 6. Пользователь и права"
id -u www-data >/dev/null 2>&1 || useradd www-data
chown -R www-data:www-data "$APP_DIR"

echo "==> 7. Включаем и запускаем сервис"
systemctl daemon-reload
systemctl enable easy-food-bot
systemctl start easy-food-bot || true

echo ""
echo "=============================================="
echo "Готово! Проверьте статус:"
echo "  systemctl status easy-food-bot"
echo "Логи:"
echo "  journalctl -u easy-food-bot -f"
echo ""
echo "Если не вписали токен — сделайте:"
echo "  nano $APP_DIR/.env"
echo "  systemctl restart easy-food-bot"
echo "=============================================="