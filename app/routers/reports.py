"""Отчёты: выгрузка CSV по метрикам, рекомендациям и экспериментам."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Ctx, accessible_location_ids, get_ctx
from ..models import Location
from ..services import analytics

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _csv(rows: list[dict], headers: list[str]) -> StreamingResponse:
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.DictWriter(buffer, fieldnames=headers, delimiter=";")
    writer.writeheader()
    for row in rows:
        writer.writerow({h: row.get(h, "") for h in headers})
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="neonpulse-report.csv"'},
    )


@router.get("/daily")
def daily_report(
    date_from: str | None = None,
    date_to: str | None = None,
    location_ids: str | None = None,
    ctx: Ctx = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    today = date.today()
    to = date.fromisoformat(date_to) if date_to else today - timedelta(days=1)
    frm = date.fromisoformat(date_from) if date_from else to - timedelta(days=27)
    allowed = accessible_location_ids(db, ctx)
    ids = [int(x) for x in (location_ids or "").split(",") if x.strip().isdigit()] or allowed
    ids = [x for x in ids if x in allowed]
    names = {loc.id: loc.name for loc in db.scalars(select(Location).where(Location.id.in_(ids))).all()}
    rows = []
    for loc_id in ids:
        for row in analytics.daily_series(db, ctx.org_id, [loc_id], frm, to):
            rows.append({"location": names.get(loc_id, loc_id), **row})
    headers = [
        "location",
        "date",
        "passersby",
        "looked",
        "approached",
        "entries",
        "receipts",
        "revenue",
        "avg_check",
        "attention_rate",
        "entry_conversion",
        "purchase_conversion",
    ]
    return _csv(rows, headers)


@router.get("/ranking")
def ranking_report(
    date_from: str | None = None,
    date_to: str | None = None,
    ctx: Ctx = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    today = date.today()
    to = date.fromisoformat(date_to) if date_to else today - timedelta(days=1)
    frm = date.fromisoformat(date_from) if date_from else to - timedelta(days=27)
    ids = accessible_location_ids(db, ctx)
    rows = analytics.location_ranking(db, ctx.org_id, ids, frm, to)
    headers = [
        "rank",
        "name",
        "city",
        "passersby",
        "entries",
        "receipts",
        "revenue",
        "avg_check",
        "entry_conversion",
        "purchase_conversion",
        "attention_rate",
    ]
    return _csv(rows, headers)
