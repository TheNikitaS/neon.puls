"""Аналитика: обзор, динамика, сравнение, профили, «до/после»."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Ctx, accessible_location_ids, ensure_location, get_ctx
from ..models import Change, Location
from ..services import analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _period(date_from: str | None, date_to: str | None, default_days: int = 28) -> tuple[date, date]:
    today = date.today()
    to = date.fromisoformat(date_to) if date_to else today - timedelta(days=1)
    frm = date.fromisoformat(date_from) if date_from else to - timedelta(days=default_days - 1)
    if frm > to:
        raise HTTPException(status_code=422, detail="Начало периода позже конца")
    return frm, to


def _scope(ctx: Ctx, db: Session, location_ids: str | None) -> list[int]:
    allowed = accessible_location_ids(db, ctx)
    if not location_ids:
        return allowed
    requested = [int(x) for x in location_ids.split(",") if x.strip().isdigit()]
    return [x for x in requested if x in allowed]


@router.get("/overview")
def overview(
    date_from: str | None = None,
    date_to: str | None = None,
    location_ids: str | None = None,
    ctx: Ctx = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    frm, to = _period(date_from, date_to)
    ids = _scope(ctx, db, location_ids)
    cmp = analytics.compare_periods(db, ctx.org_id, ids, frm, to)
    series = analytics.daily_series(db, ctx.org_id, ids, frm, to)
    ranking = analytics.location_ranking(db, ctx.org_id, ids, frm, to)
    attention_available = any(row["looked"] > 0 for row in series)
    attention_locations = [
        loc.id
        for loc in db.query(Location).filter(Location.id.in_(ids)).all()
        if getattr(loc, "attention_enabled", True)
    ] if ids else []
    return {
        **cmp,
        "series": series,
        "ranking": ranking,
        "locations_count": len(ids),
        "attention_available": attention_available,
        "attention_locations": len(attention_locations),
    }


@router.get("/series")
def series(
    date_from: str | None = None,
    date_to: str | None = None,
    location_ids: str | None = None,
    ctx: Ctx = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    frm, to = _period(date_from, date_to)
    ids = _scope(ctx, db, location_ids)
    return analytics.daily_series(db, ctx.org_id, ids, frm, to)


@router.get("/compare")
def compare(
    date_from: str | None = None,
    date_to: str | None = None,
    location_ids: str | None = None,
    ctx: Ctx = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    frm, to = _period(date_from, date_to)
    ids = _scope(ctx, db, location_ids)
    return analytics.compare_periods(db, ctx.org_id, ids, frm, to)


@router.get("/ranking")
def ranking(
    date_from: str | None = None,
    date_to: str | None = None,
    location_ids: str | None = None,
    ctx: Ctx = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    frm, to = _period(date_from, date_to)
    ids = _scope(ctx, db, location_ids)
    return analytics.location_ranking(db, ctx.org_id, ids, frm, to)


@router.get("/hourly")
def hourly(
    date_from: str | None = None,
    date_to: str | None = None,
    location_ids: str | None = None,
    ctx: Ctx = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    frm, to = _period(date_from, date_to, 14)
    ids = _scope(ctx, db, location_ids)
    return analytics.hourly_profile(db, ctx.org_id, ids, frm, to)


@router.get("/weekday")
def weekday(
    date_from: str | None = None,
    date_to: str | None = None,
    location_ids: str | None = None,
    ctx: Ctx = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    frm, to = _period(date_from, date_to, 56)
    ids = _scope(ctx, db, location_ids)
    return analytics.weekday_profile(db, ctx.org_id, ids, frm, to)


@router.get("/before-after")
def before_after(
    location_id: int,
    change_id: int | None = None,
    change_at: str | None = None,
    baseline_days: int = Query(default=14, ge=3, le=90),
    result_days: int = Query(default=14, ge=3, le=90),
    ctx: Ctx = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    ensure_location(db, ctx, location_id)
    if change_id:
        change = db.get(Change, change_id)
        if not change or change.location_id != location_id:
            raise HTTPException(status_code=404, detail="Изменение не найдено")
        moment = change.applied_at
    elif change_at:
        moment = datetime.fromisoformat(change_at)
    else:
        raise HTTPException(status_code=422, detail="Укажите change_id или change_at")
    return analytics.before_after(db, ctx.org_id, location_id, moment, baseline_days, result_days)
