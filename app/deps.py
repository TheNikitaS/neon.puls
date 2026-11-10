"""Зависимости FastAPI: текущий пользователь, организация, роли, доступ к точкам."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Location, Membership, Organization, User
from .security import decode_token

ROLE_RANK = {
    "ANALYST": 10,
    "LOCATION_MANAGER": 20,
    "REGIONAL_MANAGER": 30,
    "NETWORK_MANAGER": 40,
    "ORG_ADMIN": 50,
}


@dataclass
class Ctx:
    user: User
    org: Organization | None
    membership: Membership | None
    role: str
    is_superadmin: bool

    @property
    def org_id(self) -> int:
        if self.org is None:
            raise HTTPException(status_code=400, detail="Организация не выбрана")
        return self.org.id

    def can(self, minimum: str) -> bool:
        if self.is_superadmin:
            return True
        return ROLE_RANK.get(self.role, 0) >= ROLE_RANK.get(minimum, 999)

    def require(self, minimum: str) -> None:
        if not self.can(minimum):
            raise HTTPException(status_code=403, detail="Недостаточно прав для этого действия")


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
    return authorization.split(" ", 1)[1].strip()


def get_ctx(
    authorization: str | None = Header(default=None),
    x_org: str | None = Header(default=None, alias="X-Organization-Id"),
    db: Session = Depends(get_db),
) -> Ctx:
    payload = decode_token(_bearer(authorization))
    if not payload:
        raise HTTPException(status_code=401, detail="Сессия истекла, войдите заново")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Пользователь не найден или отключён")

    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    org_id = int(x_org) if x_org and x_org.isdigit() else payload.get("org")
    membership = next((m for m in memberships if m.organization_id == org_id), None)
    if membership is None and memberships:
        membership = memberships[0]
    if membership is None and user.is_superadmin:
        # Суперадминистратор без членства: по умолчанию первая организация платформы
        first_org = db.scalars(select(Organization).order_by(Organization.id)).first()
        if first_org is not None:
            org_id = first_org.id
    org = db.get(Organization, membership.organization_id) if membership else None
    if org is None and user.is_superadmin and org_id:
        org = db.get(Organization, int(org_id))
    role = membership.role if membership else ("SUPERADMIN" if user.is_superadmin else "ANALYST")
    return Ctx(user=user, org=org, membership=membership, role=role, is_superadmin=user.is_superadmin)


def accessible_location_ids(db: Session, ctx: Ctx) -> list[int]:
    """Изоляция данных: суперадмин видит всё, остальные — только свои точки по scope."""
    if ctx.is_superadmin and ctx.org is None:
        return [row for row in db.scalars(select(Location.id)).all()]
    if ctx.org is None:
        return []
    rows = db.scalars(select(Location).where(Location.organization_id == ctx.org.id)).all()
    scope = (ctx.membership.scope if ctx.membership else {}) or {}
    allowed = scope.get("location_ids")
    regions = scope.get("region_ids")
    if ctx.role in ("ORG_ADMIN", "NETWORK_MANAGER") or ctx.is_superadmin:
        return [loc.id for loc in rows]
    if allowed:
        return [loc.id for loc in rows if loc.id in set(allowed)]
    if regions:
        return [loc.id for loc in rows if loc.region_id in set(regions)]
    return [loc.id for loc in rows]


def ensure_location(db: Session, ctx: Ctx, location_id: int) -> Location:
    loc = db.get(Location, location_id)
    if not loc or (not ctx.is_superadmin and loc.organization_id != ctx.org_id):
        raise HTTPException(status_code=404, detail="Торговая точка не найдена")
    if location_id not in accessible_location_ids(db, ctx):
        raise HTTPException(status_code=403, detail="Нет доступа к этой точке")
    return loc
