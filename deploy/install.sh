#!/usr/bin/env bash
# Установка и автозапуск бота на VPS с Ubuntu/Debian.
# Запускать от root. Повторный запуск обновляет бота до последней версии.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Nastyface144/barbershop-bot.git}"
APP_DIR="/opt/barbershop-bot"
APP_USER="barbershop"
SERVICE="barbershop-bot"

if [ "$(id -u)" -ne 0 ]; then
    echo "Запустите скрипт от root: sudo bash install.sh"
    exit 1
fi

echo "==> Устанавливаю системные пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv git >/dev/null

echo "==> Загружаю код бота"
if [ -d "$APP_DIR/.git" ]; then
    # Папка принадлежит пользователю бота, а скрипт работает от root
    git config --global --get-all safe.directory | grep -qx "$APP_DIR" \
        || git config --global --add safe.directory "$APP_DIR"
    git -C "$APP_DIR" pull --ff-only
else
    git clone --depth 1 "$REPO_URL" "$APP_DIR"
fi

echo "==> Устанавливаю зависимости Python"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
    echo
    echo "==> Настройка бота"
    read -rp "Токен бота от @BotFather: " BOT_TOKEN </dev/tty
    read -rp "Ваш Telegram ID (от @userinfobot): " ADMIN_ID </dev/tty
    cat >"$APP_DIR/.env" <<EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_ID=$ADMIN_ID
TIMEZONE=Europe/Moscow
DB_PATH=$APP_DIR/barbershop.db
EOF
fi

echo "==> Настраиваю автозапуск"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"

cat >"/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=Barbershop Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python -m bot
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null 2>&1
systemctl restart "$SERVICE"
sleep 5

echo
if systemctl is-active --quiet "$SERVICE"; then
    echo "✅ Бот запущен и будет работать круглосуточно."
else
    echo "❌ Бот не запустился. Последние строки лога:"
fi
journalctl -u "$SERVICE" -n 15 --no-pager
echo
echo "Полезные команды:"
echo "  journalctl -u $SERVICE -f        # смотреть лог (выход: Ctrl+C)"
echo "  systemctl restart $SERVICE       # перезапустить"
echo "  nano $APP_DIR/.env               # изменить токен или ID"
