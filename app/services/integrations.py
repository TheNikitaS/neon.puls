"""Integration Hub: коннекторы, нормализация, синхронизация, журнал.

Архитектура: каждый источник — отдельный коннектор, который отдаёт записи в
едином формате (раздел 13 ТЗ). Ядро платформы не знает, откуда пришли данные.

Реальные API (Ivideon, POS) требуют ключей и проверки на аккаунте клиента.
Без ключей коннектор работает в sandbox-режиме и явно помечает это в журнале.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SANDBOX_MODE
from ..models import (
    AttentionMetric,
    Camera,
    Integration,
    IntegrationLog,
    Location,
    Transaction,
    VisitorMetric,
)
from ..security import decrypt_credentials


def log(db: Session, integration: Integration, level: str, message: str, meta: dict | None = None) -> None:
    db.add(
        IntegrationLog(
            integration_id=integration.id,
            level=level,
            message=message,
            meta=meta or {},
        )
    )


class BaseConnector:
    kind = "custom"

    def __init__(self, integration: Integration):
        self.integration = integration
        self.credentials = decrypt_credentials(integration.credentials_enc)
        self.config = integration.config or {}

    # --- служебное -----------------------------------------------------
    def _headers(self) -> dict:
        auth = self.integration.auth_type
        token = self.credentials.get("api_key") or self.credentials.get("token") or ""
        if auth == "bearer":
            return {"Authorization": f"Bearer {token}"}
        if auth == "api_key":
            header = self.credentials.get("header") or "X-API-Key"
            return {header: token}
        return {}

    def test(self) -> dict:
        raise NotImplementedError

    def fetch(self, since: datetime, until: datetime) -> list[dict]:
        raise NotImplementedError


class IvideonConnector(BaseConnector):
    """Видеоаналитика Ivideon.

    Реальный маршрут: base_url + /v1/analytics/events (уточняется в личном кабинете
    Ivideon и на тарифе клиента). Ответ приводится к нормализованному виду.
    """

    kind = "video"

    def test(self) -> dict:
        if SANDBOX_MODE or not self.integration.base_url or not self.credentials.get("api_key"):
            return {
                "ok": True,
                "mode": "sandbox",
                "message": "Sandbox-режим: ключ Ivideon не задан, данные генерируются детерминированно.",
            }
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(self.integration.base_url.rstrip("/") + "/v1/account", headers=self._headers())
            return {
                "ok": resp.status_code < 400,
                "mode": "live",
                "status_code": resp.status_code,
                "message": "Соединение установлено" if resp.status_code < 400 else f"HTTP {resp.status_code}",
            }
        except Exception as exc:  # pragma: no cover - сеть
            return {"ok": False, "mode": "live", "message": f"Ошибка соединения: {exc}"}

    def fetch(self, since: datetime, until: datetime) -> list[dict]:
        if SANDBOX_MODE or not self.integration.base_url or not self.credentials.get("api_key"):
            return self._sandbox(since, until)
        params = {
            "from": since.isoformat(),
            "to": until.isoformat(),
            "metrics": "passersby,looked,approached,entries,unique_visitors,dwell",
        }
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                self.integration.base_url.rstrip("/") + "/v1/analytics/events",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            payload = resp.json()
        return [self._normalize(item) for item in payload.get("items", [])]

    def _normalize(self, item: dict) -> dict:
        return {
            "organization_id": self.integration.organization_id,
            "location_id": item.get("location_id"),
            "source": "ivideon",
            "metric_type": item.get("metric_type", "visitor_count"),
            "timestamp": item.get("timestamp"),
            "value": item.get("value", 0),
            "unit": item.get("unit", "persons"),
            "metadata": item.get("metadata", {}),
        }

    def _sandbox(self, since: datetime, until: datetime) -> list[dict]:
        records: list[dict] = []
        locations = self.integration.config.get("location_ids") or []
        for loc_id in locations:
            rnd = random.Random(f"ivideon:{loc_id}")
            cursor = since.replace(minute=0, second=0, microsecond=0)
            while cursor <= until:
                hour = cursor.hour
                open_hour = 8 <= hour <= 21
                base = rnd.randint(18, 60) if open_hour else rnd.randint(0, 6)
                records.append(
                    {
                        "organization_id": self.integration.organization_id,
                        "location_id": loc_id,
                        "source": "ivideon",
                        "metric_type": "entries",
                        "timestamp": cursor.isoformat(),
                        "value": base,
                        "unit": "persons",
                        "metadata": {"camera_id": f"cam_{loc_id}_entrance", "zone_id": "entrance", "confidence": 0.93},
                    }
                )
                cursor += timedelta(hours=1)
        return records


class PosConnector(BaseConnector):
    """Универсальный коннектор кассовых систем.

    config.mapping описывает, как поля ответа POS превращаются в чеки:
    {"items_path": "data.receipts", "amount": "total", "ts": "closed_at", ...}
    """

    kind = "pos"

    def test(self) -> dict:
        if SANDBOX_MODE or not self.integration.base_url:
            return {
                "ok": True,
                "mode": "sandbox",
                "message": "Sandbox-режим: URL кассы не задан, чеки генерируются детерминированно.",
            }
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(self.integration.base_url.rstrip("/") + "/health", headers=self._headers())
            return {
                "ok": resp.status_code < 400,
                "mode": "live",
                "status_code": resp.status_code,
                "message": "Соединение установлено" if resp.status_code < 400 else f"HTTP {resp.status_code}",
            }
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "mode": "live", "message": f"Ошибка соединения: {exc}"}

    def fetch(self, since: datetime, until: datetime) -> list[dict]:
        if SANDBOX_MODE or not self.integration.base_url:
            return self._sandbox(since, until)
        mapping = self.config.get("mapping", {})
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                self.integration.base_url.rstrip("/") + mapping.get("path", "/receipts"),
                headers=self._headers(),
                params={"from": since.isoformat(), "to": until.isoformat()},
            )
            resp.raise_for_status()
            payload = resp.json()
        items = payload
        for key in mapping.get("items_path", "data").split("."):
            items = items.get(key, []) if isinstance(items, dict) else []
        return [
            {
                "organization_id": self.integration.organization_id,
                "location_id": item.get(mapping.get("location", "location_id")),
                "source": "pos",
                "metric_type": "sales",
                "timestamp": item.get(mapping.get("ts", "closed_at")),
                "value": item.get(mapping.get("amount", "total"), 0),
                "currency": item.get(mapping.get("currency", "currency"), "RUB"),
                "metadata": {
                    "receipt_no": item.get(mapping.get("receipt_no", "number"), ""),
                    "items_count": item.get(mapping.get("items_count", "items_count"), 0),
                    "discount": item.get(mapping.get("discount", "discount"), 0),
                    "is_return": item.get(mapping.get("is_return", "is_return"), False),
                },
            }
            for item in items
        ]

    def _sandbox(self, since: datetime, until: datetime) -> list[dict]:
        records: list[dict] = []
        locations = self.integration.config.get("location_ids") or []
        for loc_id in locations:
            rnd = random.Random(f"pos:{loc_id}")
            cursor = since
            while cursor <= until:
                if 8 <= cursor.hour <= 21:
                    for _ in range(rnd.randint(1, 4)):
                        amount = round(rnd.uniform(180, 1400), 2)
                        records.append(
                            {
                                "organization_id": self.integration.organization_id,
                                "location_id": loc_id,
                                "source": "pos",
                                "metric_type": "sales",
                                "timestamp": cursor.isoformat(),
                                "value": amount,
                                "currency": "RUB",
                                "metadata": {
                                    "receipt_no": f"{loc_id}-{cursor.strftime('%Y%m%d%H%M')}-{rnd.randint(100, 999)}",
                                    "items_count": rnd.randint(1, 5),
                                    "discount": round(amount * rnd.choice([0, 0, 0.05, 0.1]), 2),
                                    "is_return": rnd.random() < 0.02,
                                },
                            }
                        )
                cursor += timedelta(hours=1)
        return records


class CustomConnector(BaseConnector):
    """Произвольный REST-источник клиента с настраиваемым маппингом."""

    kind = "custom"

    def test(self) -> dict:
        if not self.integration.base_url:
            return {"ok": False, "mode": "live", "message": "Не задан URL источника"}
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(self.integration.base_url, headers=self._headers())
            return {
                "ok": resp.status_code < 400,
                "mode": "live",
                "status_code": resp.status_code,
                "message": "Соединение установлено" if resp.status_code < 400 else f"HTTP {resp.status_code}",
            }
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "mode": "live", "message": f"Ошибка соединения: {exc}"}

    def fetch(self, since: datetime, until: datetime) -> list[dict]:
        if not self.integration.base_url:
            return []
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                self.integration.base_url,
                headers=self._headers(),
                params={"from": since.isoformat(), "to": until.isoformat()},
            )
            resp.raise_for_status()
            payload = resp.json()
        items = payload.get("items", payload if isinstance(payload, list) else [])
        return [
            {
                "organization_id": self.integration.organization_id,
                "location_id": item.get("location_id"),
                "source": "custom",
                "metric_type": item.get("metric_type", "visitor_count"),
                "timestamp": item.get("timestamp"),
                "value": item.get("value", 0),
                "unit": item.get("unit", ""),
                "metadata": item.get("metadata", {}),
            }
            for item in items
        ]


CONNECTORS = {
    "ivideon": IvideonConnector,
    "generic_pos": PosConnector,
    "custom_rest": CustomConnector,
}


def connector_for(integration: Integration) -> BaseConnector:
    cls = CONNECTORS.get(integration.provider, CustomConnector)
    return cls(integration)


def _upsert_attention(db: Session, org_id: int, loc_id: int, ts: datetime, value: int, source: str) -> None:
    row = db.scalar(
        select(AttentionMetric).where(AttentionMetric.location_id == loc_id, AttentionMetric.ts == ts)
    )
    if row is None:
        row = AttentionMetric(organization_id=org_id, location_id=loc_id, ts=ts, source=source)
        db.add(row)
    row.passersby = max(row.passersby or 0, value)


def _upsert_visitor(db: Session, org_id: int, loc_id: int, ts: datetime, value: int, source: str) -> bool:
    row = db.scalar(select(VisitorMetric).where(VisitorMetric.location_id == loc_id, VisitorMetric.ts == ts))
    if row is None:
        row = VisitorMetric(organization_id=org_id, location_id=loc_id, ts=ts, source=source)
        db.add(row)
    elif (row.entries or 0) > 0:
        # За этот час данные уже есть — историю не перезаписываем
        return False
    row.entries = value
    row.unique_visitors = max(row.unique_visitors or 0, int(value * 0.92))
    row.dwell_avg_sec = row.dwell_avg_sec or 240.0
    return True


def apply_records(db: Session, integration: Integration, records: list[dict]) -> dict:
    """Нормализованные записи → таблицы метрик. Возвращает счётчики."""
    stats = {"records": len(records), "attention": 0, "visitors": 0, "transactions": 0, "skipped": 0, "duplicates": 0}
    org_id = integration.organization_id

    # Дни, за которые чеки уже есть: повторная синхронизация не должна их дублировать
    existing_days: set[tuple[int, str]] = set()
    loc_ids = {rec.get("location_id") for rec in records if rec.get("location_id")}
    if loc_ids:
        rows = db.execute(
            select(Transaction.location_id, Transaction.ts).where(
                Transaction.organization_id == org_id,
                Transaction.location_id.in_(loc_ids),
            )
        ).all()
        existing_days = {(loc_id, ts.date().isoformat()) for loc_id, ts in rows}

    for rec in records:
        loc_id = rec.get("location_id")
        if not loc_id or not db.get(Location, loc_id):
            stats["skipped"] += 1
            continue
        try:
            ts = datetime.fromisoformat(str(rec["timestamp"]).replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            stats["skipped"] += 1
            continue
        metric = rec.get("metric_type")
        value = rec.get("value", 0)
        if metric in ("passersby", "traffic"):
            _upsert_attention(db, org_id, loc_id, ts.replace(minute=0, second=0, microsecond=0), int(value), rec.get("source", ""))
            stats["attention"] += 1
        elif metric in ("entries", "visitor_count"):
            if _upsert_visitor(db, org_id, loc_id, ts.replace(minute=0, second=0, microsecond=0), int(value), rec.get("source", "")):
                stats["visitors"] += 1
            else:
                stats["duplicates"] += 1
        elif metric == "sales":
            if (loc_id, ts.date().isoformat()) in existing_days:
                stats["duplicates"] += 1
                continue
            meta = rec.get("metadata", {})
            db.add(
                Transaction(
                    organization_id=org_id,
                    location_id=loc_id,
                    ts=ts,
                    receipt_no=str(meta.get("receipt_no", "")),
                    amount=float(value or 0),
                    items_count=int(meta.get("items_count", 0) or 0),
                    discount=float(meta.get("discount", 0) or 0),
                    is_return=bool(meta.get("is_return", False)),
                    categories=meta.get("categories", []),
                    source=rec.get("source", "pos"),
                )
            )
            stats["transactions"] += 1
        else:
            stats["skipped"] += 1
    db.commit()
    return stats


def test_connection(db: Session, integration: Integration) -> dict:
    result = connector_for(integration).test()
    log(db, integration, "info" if result.get("ok") else "error", f"Проверка соединения: {result.get('message')}", result)
    if result.get("ok"):
        integration.status = "connected"
        integration.last_error = ""
    else:
        integration.status = "error"
        integration.last_error = result.get("message", "")
    db.commit()
    return result


def run_sync(db: Session, integration: Integration, days: int = 3) -> dict:
    until = datetime.now().replace(minute=0, second=0, microsecond=0)
    since = until - timedelta(days=days)
    connector = connector_for(integration)
    try:
        records = connector.fetch(since, until)
        stats = apply_records(db, integration, records)
        integration.status = "connected"
        integration.last_sync_at = datetime.utcnow()
        integration.last_error = ""
        log(
            db,
            integration,
            "info",
            f"Синхронизация завершена: {stats['records']} записей, "
            f"внимание {stats['attention']}, посещения {stats['visitors']}, чеки {stats['transactions']}",
            stats,
        )
        db.commit()
        return {"ok": True, **stats}
    except Exception as exc:
        integration.status = "error"
        integration.last_error = str(exc)
        log(db, integration, "error", f"Ошибка синхронизации: {exc}")
        db.commit()
        return {"ok": False, "error": str(exc)}


def ensure_cameras(db: Session, integration: Integration) -> int:
    """Привязка камер к точкам по конфигурации интеграции."""
    created = 0
    for loc_id in integration.config.get("location_ids", []):
        exists = db.scalar(select(Camera).where(Camera.location_id == loc_id, Camera.provider == integration.provider))
        if exists:
            continue
        db.add(
            Camera(
                location_id=loc_id,
                name=f"Камера входа · точка {loc_id}",
                external_id=f"{integration.provider}_{loc_id}_entrance",
                provider=integration.provider,
                purpose="entrance",
                status="online",
                last_seen_at=datetime.utcnow(),
            )
        )
        created += 1
    db.commit()
    return created
