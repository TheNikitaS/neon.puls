"""Провайдеры LLM. Основной — YandexGPT через Yandex Cloud Foundation Models.

Расчётная часть AI-ядра остаётся детерминированной: модель только формулирует
текст по готовым фактам и не получает права придумывать числа.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from ..config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_PROVIDER,
    YANDEX_API_KEY,
    YANDEX_ENDPOINT,
    YANDEX_FOLDER_ID,
    YANDEX_IAM_TOKEN,
    YANDEX_MODEL,
)

SYSTEM_PROMPT = (
    "Ты аналитик офлайн-ритейла в платформе НЕОН.ПУЛЬС. Отвечай по-русски, коротко и по делу. "
    "Опирайся ТОЛЬКО на переданные факты и не выдумывай числа. "
    "Учитывай локальный контекст точки: адрес, район и описанную целевую аудиторию (ЦА). "
    "Если данных не хватает — скажи об этом прямо. "
    "Не выдавай гипотезу за доказанную причину: указывай уверенность и ограничения."
)


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str


def provider_name() -> str:
    return LLM_PROVIDER


def is_configured() -> bool:
    if LLM_PROVIDER == "yandexgpt":
        return bool(YANDEX_FOLDER_ID and (YANDEX_API_KEY or YANDEX_IAM_TOKEN))
    if LLM_PROVIDER == "llm":
        return bool(LLM_BASE_URL and LLM_API_KEY)
    return False


def _yandex(prompt: str, facts: dict) -> LLMResult | None:
    if not is_configured():
        return None
    token = YANDEX_API_KEY or YANDEX_IAM_TOKEN
    auth_header = f"Api-Key {token}" if YANDEX_API_KEY else f"Bearer {token}"
    body = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/{YANDEX_MODEL}/latest",
        "completionOptions": {"stream": False, "temperature": 0.2, "maxTokens": "900"},
        "messages": [
            {"role": "system", "text": SYSTEM_PROMPT},
            {
                "role": "user",
                "text": f"{prompt}\n\nФакты (JSON):\n{json.dumps(facts, ensure_ascii=False)}",
            },
        ],
    }
    try:
        with httpx.Client(timeout=40) as client:
            resp = client.post(
                YANDEX_ENDPOINT,
                headers={"Authorization": auth_header, "Content-Type": "application/json"},
                json=body,
            )
            resp.raise_for_status()
            payload = resp.json()
        text = payload["result"]["alternatives"][0]["message"]["text"].strip()
        return LLMResult(text=text, provider="yandexgpt", model=YANDEX_MODEL)
    except Exception:
        return None


def _openai_compatible(prompt: str, facts: dict) -> LLMResult | None:
    if not is_configured():
        return None
    try:
        with httpx.Client(timeout=40) as client:
            resp = client.post(
                LLM_BASE_URL.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={
                    "model": LLM_MODEL or "default",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": f"{prompt}\n\nФакты (JSON):\n{json.dumps(facts, ensure_ascii=False)}",
                        },
                    ],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
        return LLMResult(text=text, provider="llm", model=LLM_MODEL or "default")
    except Exception:
        return None


def complete(prompt: str, facts: dict) -> LLMResult | None:
    """Возвращает текст модели или None — тогда используется детерминированный ответ."""
    if LLM_PROVIDER == "yandexgpt":
        return _yandex(prompt, facts)
    if LLM_PROVIDER == "llm":
        return _openai_compatible(prompt, facts)
    return None


def status() -> dict:
    return {
        "provider": LLM_PROVIDER,
        "configured": is_configured(),
        "yandex_folder": bool(YANDEX_FOLDER_ID),
        "yandex_model": YANDEX_MODEL if LLM_PROVIDER == "yandexgpt" else None,
        "fallback": "rules",
    }
