"""Регистрация, вход, профиль, переключение организации."""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Ctx, get_ctx
from ..models import Membership, Organization, Subscription, User
from ..schemas import LoginIn, RegisterIn
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "company"
    candidate = base
    idx = 1
    while True:
        yield candidate
        idx += 1
        candidate = f"{base}-{idx}"


def _orgs_for(db: Session, user: User) -> list[dict]:
    rows = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    out = []
    for m in rows:
        org = db.get(Organization, m.organization_id)
        if org:
            out.append({"id": org.id, "name": org.name, "role": m.role, "plan": org.plan})
    return out


def _payload(db: Session, user: User, org_id: int | None) -> dict:
    orgs = _orgs_for(db, user)
    active = org_id or (orgs[0]["id"] if orgs else None)
    return {
        "token": create_token(user.id, active, user.is_superadmin),
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "position": user.position,
            "is_superadmin": user.is_superadmin,
        },
        "organizations": orgs,
        "active_org_id": active,
    }


@router.post("/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")
    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        position="Администратор компании",
    )
    db.add(user)
    db.flush()
    slug = next(s for s in _slug(data.company_name) if not db.scalar(select(Organization).where(Organization.slug == s)))
    org = Organization(name=data.company_name, slug=slug, industry=data.industry, plan="trial")
    db.add(org)
    db.flush()
    db.add(Membership(user_id=user.id, organization_id=org.id, role="ORG_ADMIN", scope={}))
    db.add(Subscription(organization_id=org.id, plan="trial", seats=5, locations_limit=10, price_month=0))
    db.commit()
    return _payload(db, user, org.id)


@router.post("/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Пользователь отключён")
    user.last_login_at = datetime.utcnow()
    db.commit()
    return _payload(db, user, None)


@router.get("/me")
def me(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    return {
        "user": {
            "id": ctx.user.id,
            "email": ctx.user.email,
            "full_name": ctx.user.full_name,
            "position": ctx.user.position,
            "is_superadmin": ctx.user.is_superadmin,
        },
        "organization": {
            "id": ctx.org.id,
            "name": ctx.org.name,
            "plan": ctx.org.plan,
            "industry": ctx.org.industry,
        }
        if ctx.org
        else None,
        "role": ctx.role,
        "organizations": _orgs_for(db, ctx.user),
    }


@router.post("/switch/{org_id}")
def switch(org_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    membership = db.scalar(
        select(Membership).where(Membership.user_id == ctx.user.id, Membership.organization_id == org_id)
    )
    if not membership and not ctx.user.is_superadmin:
        raise HTTPException(status_code=403, detail="Нет доступа к этой организации")
    return _payload(db, ctx.user, org_id)
