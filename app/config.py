"""Конфигурация приложения. Всё, что можно переопределить — через переменные окружения."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("NEONPULSE_DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

def _normalize_db_url(url: str) -> str:
    """PaaS обычно отдаёт postgres:// — SQLAlchemy нужен драйвер psycopg."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


DATABASE_URL = _normalize_db_url(
    os.getenv("DATABASE_URL", "sqlite:///" + (DATA_DIR / "neonpulse.db").as_posix())
)

_SECRET_FILE = DATA_DIR / "jwt_secret.txt"


def _load_secret() -> str:
    env = os.getenv("NEONPULSE_SECRET")
    if env:
        return env
    if _SECRET_FILE.exists():
        value = _SECRET_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = secrets.token_urlsafe(48)
    _SECRET_FILE.write_text(value, encoding="utf-8")
    return value


SECRET_KEY = _load_secret()
TOKEN_TTL_MINUTES = int(os.getenv("NEONPULSE_TOKEN_TTL_MIN", "720"))

# Провайдер AI: rules (детерминированное ядро) | llm (внешняя модель через адаптер)
LLM_PROVIDER = os.getenv("NEONPULSE_LLM_PROVIDER", "rules")
LLM_BASE_URL = os.getenv("NEONPULSE_LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("NEONPULSE_LLM_API_KEY", "")
LLM_MODEL = os.getenv("NEONPULSE_LLM_MODEL", "")

# Yandex Cloud Foundation Models (YandexGPT)
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "")
YANDEX_IAM_TOKEN = os.getenv("YANDEX_IAM_TOKEN", "")
YANDEX_MODEL = os.getenv("YANDEX_MODEL", "yandexgpt-lite")
YANDEX_ENDPOINT = os.getenv(
    "YANDEX_ENDPOINT", "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
)

# Демо-режим: коннекторы без реальных ключей работают на детерминированном sandbox-потоке
SANDBOX_MODE = os.getenv("NEONPULSE_SANDBOX", "1") not in ("0", "false", "False")

APP_NAME = "НЕОН.ПУЛЬС"
APP_TAGLINE = "AI-платформа аналитики эффективности офлайн-бизнеса"
