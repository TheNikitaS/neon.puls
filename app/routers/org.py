"""Организация, сотрудники, роли, регионы."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Ctx, get_ctx
from ..models import AuditLog, Location, Membership, Region, Subscription, User
from ..schemas import MemberIn, MemberPatch
from ..security import hash_password

router = APIRouter(prefix="/api/org", tags=["organization"])


@router.get("")
def get_org(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscription).where(Subscription.organization_id == ctx.org_id))
    return {
        "id": ctx.org.id,
        "name": ctx.org.name,
        "slug": ctx.org.slug,
        "industry": ctx.org.industry,
        "plan": ctx.org.plan,
        "status": ctx.org.status,
        "role": ctx.role,
        "subscription": {
            "plan": sub.plan,
            "status": sub.status,
            "seats": sub.seats,
            "locations_limit": sub.locations_limit,
            "price_month": sub.price_month,
            "currency": sub.currency,
        }
        if sub
        else None,
    }


@router.get("/members")
def members(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    rows = db.scalars(select(Membership).where(Membership.organization_id == ctx.org_id)).all()
    out = []
    for m in rows:
        user = db.get(User, m.user_id)
        if not user:
            continue
        out.append(
            {
                "membership_id": m.id,
                "user_id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "position": user.position,
                "role": m.role,
                "scope": m.scope,
                "is_active": user.is_active,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            }
        )
    return out


@router.post("/members")
def add_member(data: MemberIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("ORG_ADMIN")
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if user is None:
        user = User(
            email=data.email.lower(),
            password_hash=hash_password(data.password or "ChangeMe123!"),
            full_name=data.full_name,
            position="",
        )
        db.add(user)
        db.flush()
    if db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.organization_id == ctx.org_id)):
        raise HTTPException(status_code=409, detail="Пользователь уже состоит в организации")
    db.add(Membership(user_id=user.id, organization_id=ctx.org_id, role=data.role, scope=data.scope))
    db.add(AuditLog(organization_id=ctx.org_id, user_id=ctx.user.id, action="member.add", entity="user", entity_id=str(user.id)))
    db.commit()
    return {"ok": True, "user_id": user.id}


@router.patch("/members/{membership_id}")
def patch_member(membership_id: int, data: MemberPatch, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("ORG_ADMIN")
    m = db.get(Membership, membership_id)
    if not m or m.organization_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Участник не найден")
    if data.role:
        m.role = data.role
    if data.scope is not None:
        m.scope = data.scope
    if data.is_active is not None:
        user = db.get(User, m.user_id)
        if user:
            user.is_active = data.is_active
    db.add(AuditLog(organization_id=ctx.org_id, user_id=ctx.user.id, action="member.update", entity="membership", entity_id=str(m.id)))
    db.commit()
    return {"ok": True}


@router.get("/regions")
def regions(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    rows = db.scalars(select(Region).where(Region.organization_id == ctx.org_id)).all()
    counts = {}
    for loc in db.scalars(select(Location).where(Location.organization_id == ctx.org_id)).all():
        counts[loc.region_id] = counts.get(loc.region_id, 0) + 1
    return [{"id": r.id, "name": r.name, "code": r.code, "locations": counts.get(r.id, 0)} for r in rows]


@router.post("/regions")
def add_region(body: dict, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("ORG_ADMIN")
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Укажите название региона")
    region = Region(organization_id=ctx.org_id, name=name, code=body.get("code", ""))
    db.add(region)
    db.commit()
    return {"id": region.id, "name": region.name}


@router.get("/audit")
def audit(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("ORG_ADMIN")
    rows = db.scalars(
        select(AuditLog).where(AuditLog.organization_id == ctx.org_id).order_by(AuditLog.created_at.desc()).limit(100)
    ).all()
    return [
        {
            "id": r.id,
            "action": r.action,
            "entity": r.entity,
            "entity_id": r.entity_id,
            "user_id": r.user_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
