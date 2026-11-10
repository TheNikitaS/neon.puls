#!/usr/bin/env bash
# Установка НЕОН.ПУЛЬС на Ubuntu 22.04/24.04 без контейнеров.
# Запуск от root из каталога проекта: sudo bash deploy/install.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/neonpulse}"
APP_USER="${APP_USER:-neonpulse}"
DB_NAME="${DB_NAME:-neonpulse}"
DB_USER="${DB_USER:-neonpulse}"
PORT="${PORT:-8010}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Запустите от root: sudo bash deploy/install.sh"
  exit 1
fi

if [[ ! -f "${APP_DIR}/requirements.txt" ]]; then
  echo "Не найден ${APP_DIR}/requirements.txt — сначала скопируйте проект в ${APP_DIR}"
  exit 1
fi

echo "== 1/7 Пакеты =="
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3-pip postgresql nginx curl

echo "== 2/7 Пользователь =="
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "${APP_USER}"
fi

echo "== 3/7 База данных =="
DB_PASSWORD="${DB_PASSWORD:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')}"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';"
else
  sudo -u postgres psql -c "ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';"
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
  sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
fi

echo "== 4/7 Окружение =="
SECRET="${NEONPULSE_SECRET:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')}"
cat > /etc/neonpulse.env <<EOF
DATABASE_URL=postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@127.0.0.1:5432/${DB_NAME}
NEONPULSE_SECRET=${SECRET}
NEONPULSE_SANDBOX=${NEONPULSE_SANDBOX:-1}
NEONPULSE_LLM_PROVIDER=${NEONPULSE_LLM_PROVIDER:-rules}
YANDEX_FOLDER_ID=${YANDEX_FOLDER_ID:-}
YANDEX_API_KEY=${YANDEX_API_KEY:-}
YANDEX_MODEL=${YANDEX_MODEL:-yandexgpt-lite}
EOF
chmod 600 /etc/neonpulse.env

echo "== 5/7 Зависимости =="
python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo "== 6/7 systemd =="
install -m 644 "${APP_DIR}/deploy/neonpulse.service" /etc/systemd/system/neonpulse.service
systemctl daemon-reload
systemctl enable --now neonpulse

echo "== 7/7 nginx =="
install -m 644 "${APP_DIR}/deploy/nginx.conf" /etc/nginx/sites-available/neonpulse
ln -sf /etc/nginx/sites-available/neonpulse /etc/nginx/sites-enabled/neonpulse
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo
echo "Готово. Проверка:"
sleep 3
curl -fsS "http://127.0.0.1:${PORT}/api/health" || true
echo
echo "Пароль БД и секрет сохранены в /etc/neonpulse.env (chmod 600)."
echo "Логи: journalctl -u neonpulse -f"
