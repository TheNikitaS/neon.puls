"""Уведомления и мониторинг."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Ctx, accessible_location_ids, get_ctx
from ..models import Location, Notification
from ..services import notifications as svc

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(unread_only: bool = False, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ids = accessible_location_ids(db, ctx)
    stmt = select(Notification).where(Notification.organization_id == ctx.org_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    rows = db.scalars(stmt.order_by(Notification.created_at.desc()).limit(100)).all()
    names = {loc.id: loc.name for loc in db.scalars(select(Location).where(Location.id.in_(ids))).all()}
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "severity": r.severity,
            "title": r.title,
            "body": r.body,
            "location": names.get(r.location_id, ""),
            "created_at": r.created_at.isoformat(),
            "read": r.read_at is not None,
        }
        for r in rows
    ]


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    row = db.get(Notification, notification_id)
    if not row or row.organization_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    row.read_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/scan")
def scan(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ids = accessible_location_ids(db, ctx)
    created = svc.scan_anomalies(db, ctx.org_id, ids)
    created += svc.check_integration_health(db, ctx.org_id)
    return {"created": len(created), "items": [{"id": n.id, "title": n.title} for n in created]}
