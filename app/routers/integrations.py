"""Integration Hub: управление источниками данных."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Ctx, get_ctx
from ..models import Integration, IntegrationLog
from ..schemas import IntegrationIn, IntegrationPatch
from ..security import decrypt_credentials, encrypt_credentials, mask_secret
from ..services import integrations as hub

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

CATALOG = [
    {
        "provider": "ivideon",
        "kind": "video",
        "name": "Ivideon",
        "description": "Видеоаналитика: трафик, входы, внимание к витрине, зоны наблюдения.",
        "auth": ["api_key", "bearer"],
        "fields": ["base_url", "api_key"],
    },
    {
        "provider": "generic_pos",
        "kind": "pos",
        "name": "Касса / POS (универсальный)",
        "description": "Чеки, выручка, средний чек, возвраты. Маппинг полей настраивается.",
        "auth": ["api_key", "bearer", "oauth2"],
        "fields": ["base_url", "api_key", "mapping"],
    },
    {
        "provider": "custom_rest",
        "kind": "custom",
        "name": "Свой REST API",
        "description": "Любой источник клиента: CRM, ERP, товарный учёт, собственные сервисы.",
        "auth": ["api_key", "bearer", "oauth2", "none"],
        "fields": ["base_url", "api_key"],
    },
]


def _serialize(item: Integration) -> dict:
    creds = decrypt_credentials(item.credentials_enc)
    return {
        "id": item.id,
        "kind": item.kind,
        "provider": item.provider,
        "name": item.name,
        "base_url": item.base_url,
        "auth_type": item.auth_type,
        "credentials_preview": {k: mask_secret(str(v)) for k, v in creds.items() if k != "header"},
        "config": item.config,
        "status": item.status,
        "sync_interval_min": item.sync_interval_min,
        "last_sync_at": item.last_sync_at.isoformat() if item.last_sync_at else None,
        "last_error": item.last_error,
        "created_at": item.created_at.isoformat(),
    }


@router.get("/catalog")
def catalog():
    return CATALOG


@router.get("")
def list_integrations(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Integration).where(Integration.organization_id == ctx.org_id).order_by(Integration.created_at)
    ).all()
    return [_serialize(r) for r in rows]


@router.post("")
def create_integration(data: IntegrationIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("ORG_ADMIN")
    item = Integration(
        organization_id=ctx.org_id,
        kind=data.kind,
        provider=data.provider,
        name=data.name,
        base_url=data.base_url,
        auth_type=data.auth_type,
        credentials_enc=encrypt_credentials(data.credentials),
        config=data.config,
        sync_interval_min=data.sync_interval_min,
        status="draft",
    )
    db.add(item)
    db.flush()
    hub.log(db, item, "info", "Интеграция создана")
    db.commit()
    return _serialize(item)


@router.patch("/{integration_id}")
def patch_integration(
    integration_id: int, data: IntegrationPatch, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)
):
    ctx.require("ORG_ADMIN")
    item = db.get(Integration, integration_id)
    if not item or item.organization_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Интеграция не найдена")
    payload = data.model_dump(exclude_unset=True)
    if "credentials" in payload and payload["credentials"] is not None:
        merged = decrypt_credentials(item.credentials_enc)
        merged.update(payload.pop("credentials"))
        item.credentials_enc = encrypt_credentials(merged)
    for field, value in payload.items():
        setattr(item, field, value)
    hub.log(db, item, "info", "Настройки интеграции обновлены")
    db.commit()
    return _serialize(item)


@router.post("/{integration_id}/test")
def test_integration(integration_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    item = db.get(Integration, integration_id)
    if not item or item.organization_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Интеграция не найдена")
    return hub.test_connection(db, item)


@router.post("/{integration_id}/sync")
def sync_integration(integration_id: int, days: int = 3, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    item = db.get(Integration, integration_id)
    if not item or item.organization_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Интеграция не найдена")
    result = hub.run_sync(db, item, days)
    if item.kind == "video":
        hub.ensure_cameras(db, item)
    return result


@router.get("/{integration_id}/logs")
def logs(integration_id: int, limit: int = 50, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    item = db.get(Integration, integration_id)
    if not item or item.organization_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Интеграция не найдена")
    rows = db.scalars(
        select(IntegrationLog)
        .where(IntegrationLog.integration_id == integration_id)
        .order_by(IntegrationLog.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "level": r.level,
            "message": r.message,
            "meta": r.meta,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.delete("/{integration_id}")
def delete_integration(integration_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("ORG_ADMIN")
    item = db.get(Integration, integration_id)
    if not item or item.organization_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Интеграция не найдена")
    db.delete(item)
    db.commit()
    return {"ok": True}
