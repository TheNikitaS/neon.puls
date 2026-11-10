"""Административная панель платформы (суперадминистратор Неон.Пульс)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Ctx, get_ctx
from ..models import (
    AiInsight,
    Integration,
    Location,
    Membership,
    Organization,
    Recommendation,
    Subscription,
    Transaction,
    User,
    VisitorMetric,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _guard(ctx: Ctx) -> None:
    if not ctx.is_superadmin:
        raise HTTPException(status_code=403, detail="Доступ только для администратора платформы")


@router.get("/stats")
def stats(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    _guard(ctx)
    return {
        "organizations": db.scalar(select(func.count(Organization.id))) or 0,
        "users": db.scalar(select(func.count(User.id))) or 0,
        "locations": db.scalar(select(func.count(Location.id))) or 0,
        "integrations": db.scalar(select(func.count(Integration.id))) or 0,
        "integrations_error": db.scalar(
            select(func.count(Integration.id)).where(Integration.status == "error")
        )
        or 0,
        "transactions": db.scalar(select(func.count(Transaction.id))) or 0,
        "visitor_rows": db.scalar(select(func.count(VisitorMetric.id))) or 0,
        "insights": db.scalar(select(func.count(AiInsight.id))) or 0,
        "recommendations": db.scalar(select(func.count(Recommendation.id))) or 0,
    }


@router.get("/organizations")
def organizations(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    _guard(ctx)
    out = []
    for org in db.scalars(select(Organization).order_by(Organization.created_at.desc())).all():
        sub = db.scalar(select(Subscription).where(Subscription.organization_id == org.id))
        out.append(
            {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "plan": org.plan,
                "status": org.status,
                "created_at": org.created_at.isoformat(),
                "locations": db.scalar(select(func.count(Location.id)).where(Location.organization_id == org.id)) or 0,
                "users": db.scalar(select(func.count(Membership.id)).where(Membership.organization_id == org.id)) or 0,
                "subscription": {
                    "plan": sub.plan,
                    "status": sub.status,
                    "seats": sub.seats,
                    "locations_limit": sub.locations_limit,
                    "price_month": sub.price_month,
                }
                if sub
                else None,
            }
        )
    return out


@router.get("/users")
def users(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    _guard(ctx)
    rows = db.scalars(select(User).order_by(User.created_at.desc())).all()
    orgs = {o.id: o.name for o in db.scalars(select(Organization)).all()}
    out = []
    for user in rows:
        memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
        out.append(
            {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_superadmin": user.is_superadmin,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                "organizations": [{"id": m.organization_id, "name": orgs.get(m.organization_id, ""), "role": m.role} for m in memberships],
            }
        )
    return out


@router.get("/integrations")
def integrations(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    _guard(ctx)
    orgs = {o.id: o.name for o in db.scalars(select(Organization)).all()}
    rows = db.scalars(select(Integration).order_by(Integration.created_at.desc())).all()
    return [
        {
            "id": r.id,
            "organization": orgs.get(r.organization_id, ""),
            "name": r.name,
            "provider": r.provider,
            "kind": r.kind,
            "status": r.status,
            "last_sync_at": r.last_sync_at.isoformat() if r.last_sync_at else None,
            "last_error": r.last_error,
        }
        for r in rows
    ]


@router.patch("/organizations/{org_id}")
def patch_org(org_id: int, body: dict, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    _guard(ctx)
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    for field in ("plan", "status", "name"):
        if field in body:
            setattr(org, field, body[field])
    sub = db.scalar(select(Subscription).where(Subscription.organization_id == org_id))
    if sub and "plan" in body:
        sub.plan = body["plan"]
    db.commit()
    return {"ok": True}
