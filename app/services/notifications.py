"""Уведомления и мониторинг аномалий."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Location, Notification
from . import analytics


def push(
    db: Session,
    org_id: int,
    title: str,
    body: str = "",
    kind: str = "anomaly",
    severity: str = "warning",
    location_id: int | None = None,
    meta: dict | None = None,
) -> Notification:
    row = Notification(
        organization_id=org_id,
        location_id=location_id,
        kind=kind,
        severity=severity,
        title=title,
        body=body,
        meta=meta or {},
    )
    db.add(row)
    db.commit()
    return row


def scan_anomalies(db: Session, org_id: int, location_ids: list[int]) -> list[Notification]:
    created: list[Notification] = []
    for loc_id in location_ids:
        loc = db.get(Location, loc_id)
        if not loc:
            continue
        for item in analytics.anomalies(db, org_id, [loc_id]):
            metric = "выручке" if item["metric"] == "revenue" else "входам"
            direction = "выше" if item["direction"] == "up" else "ниже"
            title = f"{loc.name}: отклонение по {metric}"
            body = (
                f"Значение {item['value']} {direction} среднего {item['mean']} "
                f"(z = {item['z_score']}). Проверьте данные и события в точке."
            )
            exists = db.scalar(
                select(Notification).where(
                    Notification.organization_id == org_id,
                    Notification.location_id == loc_id,
                    Notification.title == title,
                    Notification.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
                )
            )
            if exists:
                continue
            created.append(push(db, org_id, title, body, "anomaly", "warning", loc_id, item))
    return created


def check_integration_health(db: Session, org_id: int) -> list[Notification]:
    from ..models import Integration

    created: list[Notification] = []
    broken = db.scalars(
        select(Integration).where(Integration.organization_id == org_id, Integration.status == "error")
    ).all()
    for integration in broken:
        title = f"Интеграция «{integration.name}» не работает"
        exists = db.scalar(
            select(Notification).where(
                Notification.organization_id == org_id,
                Notification.title == title,
                Notification.read_at.is_(None),
            )
        )
        if exists:
            continue
        created.append(
            push(db, org_id, title, integration.last_error or "Источник данных недоступен", "integration", "critical")
        )
    return created
