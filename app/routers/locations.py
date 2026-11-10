"""Торговые точки, камеры, зоны, зафиксированные изменения."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Ctx, accessible_location_ids, ensure_location, get_ctx
from ..models import (
    AudienceSegment,
    Camera,
    CameraZone,
    Change,
    Hypothesis,
    Location,
    ManualDailyMetric,
    PhotoAudit,
    PilotSettings,
    PointScore,
    Region,
    TestPlan,
    Trend,
)
from ..schemas import (
    AudienceIn,
    CameraIn,
    ChangeIn,
    HypothesisIn,
    LocationIn,
    LocationPatch,
    ManualMetricIn,
    PhotoAuditIn,
    PilotIn,
    ScoreIn,
    TestPlanIn,
    TrendIn,
)

router = APIRouter(prefix="/api/locations", tags=["locations"])

SCORE_WEIGHTS = {
    "visibility": ("Видимость с расстояния", 1.2),
    "readability": ("Читаемость вывески", 1.1),
    "contrast": ("Контраст с окружением", 1.0),
    "light": ("Световой объём", 1.0),
    "entrance": ("Понятность входа", 1.0),
    "impulse": ("Импульсность", 0.9),
    "photo": ("Фото/видео привлекательность", 0.7),
    "audience": ("Соответствие ЦА", 1.0),
    "season": ("Сезонность", 0.6),
    "scale": ("Потенциал масштабирования", 0.8),
}


def _score_index(scores: dict) -> tuple[float, str]:
    total = 0.0
    weight_sum = 0.0
    for key, (_label, weight) in SCORE_WEIGHTS.items():
        value = scores.get(key)
        if value is None:
            continue
        total += float(value) * weight
        weight_sum += weight
    if not weight_sum:
        return 0.0, "Заполните оценки"
    index = round(total / weight_sum, 2)
    if index < 2.5:
        text = "Точка визуально слабая"
    elif index < 3.5:
        text = "Есть база, но много потерь"
    elif index < 4.3:
        text = "Хорошая точка, можно усиливать"
    else:
        text = "Сильная точка, задача — оптимизация и тесты"
    return index, text


@router.get("")
def list_locations(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ids = accessible_location_ids(db, ctx)
    rows = db.scalars(select(Location).where(Location.id.in_(ids)).order_by(Location.city, Location.name)).all()
    regions = {r.id: r.name for r in db.scalars(select(Region).where(Region.organization_id == ctx.org_id)).all()}
    cameras = db.scalars(select(Camera).where(Camera.location_id.in_(ids))).all() if ids else []
    cam_count: dict[int, int] = {}
    for cam in cameras:
        cam_count[cam.location_id] = cam_count.get(cam.location_id, 0) + 1
    return [
        {
            "id": loc.id,
            "public_id": loc.public_id,
            "name": loc.name,
            "city": loc.city,
            "address": loc.address,
            "status": loc.status,
            "region_id": loc.region_id,
            "region": regions.get(loc.region_id, ""),
            "area_m2": loc.area_m2,
            "cameras": cam_count.get(loc.id, 0),
        }
        for loc in rows
    ]


@router.post("")
def create_location(data: LocationIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("NETWORK_MANAGER")
    loc = Location(
        organization_id=ctx.org_id,
        name=data.name,
        city=data.city,
        address=data.address,
        region_id=data.region_id,
        status=data.status,
        area_m2=data.area_m2,
    )
    db.add(loc)
    db.commit()
    return {"id": loc.id, "public_id": loc.public_id}


@router.get("/{location_id}")
def get_location(location_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    loc = ensure_location(db, ctx, location_id)
    cameras = db.scalars(select(Camera).where(Camera.location_id == loc.id)).all()
    changes = db.scalars(
        select(Change).where(Change.location_id == loc.id).order_by(Change.applied_at.desc()).limit(20)
    ).all()
    return {
        "id": loc.id,
        "public_id": loc.public_id,
        "name": loc.name,
        "city": loc.city,
        "address": loc.address,
        "status": loc.status,
        "region_id": loc.region_id,
        "area_m2": loc.area_m2,
        "timezone": loc.timezone,
        "cameras": [
            {
                "id": c.id,
                "name": c.name,
                "external_id": c.external_id,
                "provider": c.provider,
                "purpose": c.purpose,
                "status": c.status,
                "last_seen_at": c.last_seen_at.isoformat() if c.last_seen_at else None,
                "zones": [{"id": z.id, "name": z.name, "kind": z.kind} for z in c.zones],
            }
            for c in cameras
        ],
        "changes": [
            {
                "id": ch.id,
                "kind": ch.kind,
                "title": ch.title,
                "description": ch.description,
                "applied_at": ch.applied_at.isoformat(),
            }
            for ch in changes
        ],
    }


@router.patch("/{location_id}")
def patch_location(location_id: int, data: LocationPatch, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("NETWORK_MANAGER")
    loc = ensure_location(db, ctx, location_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(loc, field, value)
    db.commit()
    return {"ok": True}


@router.post("/{location_id}/cameras")
def add_camera(location_id: int, data: CameraIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("NETWORK_MANAGER")
    ensure_location(db, ctx, location_id)
    cam = Camera(
        location_id=location_id,
        name=data.name,
        external_id=data.external_id,
        provider=data.provider,
        purpose=data.purpose,
        status=data.status,
    )
    db.add(cam)
    db.flush()
    db.add(CameraZone(camera_id=cam.id, name="Зона входа", kind="entry", polygon=[]))
    db.commit()
    return {"id": cam.id}


@router.post("/{location_id}/changes")
def add_change(location_id: int, data: ChangeIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    change = Change(
        organization_id=ctx.org_id,
        location_id=location_id,
        kind=data.kind,
        title=data.title,
        description=data.description,
        applied_at=data.applied_at,
        created_by=ctx.user.id,
    )
    db.add(change)
    db.commit()
    return {"id": change.id}


@router.get("/{location_id}/changes")
def list_changes(location_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ensure_location(db, ctx, location_id)
    rows = db.scalars(
        select(Change).where(Change.location_id == location_id).order_by(Change.applied_at.desc())
    ).all()
    return [
        {
            "id": c.id,
            "kind": c.kind,
            "title": c.title,
            "description": c.description,
            "applied_at": c.applied_at.isoformat(),
        }
        for c in rows
    ]


# ---------- пилот точки ----------


@router.get("/{location_id}/pilot")
def get_pilot(location_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    loc = ensure_location(db, ctx, location_id)
    row = db.scalar(select(PilotSettings).where(PilotSettings.location_id == location_id))
    if row is None:
        return {
            "location_id": location_id,
            "signage_date": None,
            "camera_date": None,
            "compare_days": 60,
            "avg_check": 0.0,
            "target_growth": 0.3,
            "min_days_before": 30,
            "min_days_after": 30,
            "point_name": loc.name,
            "address": loc.address,
            "comment": "",
        }
    return {
        "location_id": location_id,
        "signage_date": row.signage_date.isoformat() if row.signage_date else None,
        "camera_date": row.camera_date.isoformat() if row.camera_date else None,
        "compare_days": row.compare_days,
        "avg_check": row.avg_check,
        "target_growth": row.target_growth,
        "min_days_before": row.min_days_before,
        "min_days_after": row.min_days_after,
        "point_name": row.point_name or loc.name,
        "address": row.address or loc.address,
        "comment": row.comment,
    }


@router.put("/{location_id}/pilot")
def put_pilot(location_id: int, data: PilotIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    row = db.scalar(select(PilotSettings).where(PilotSettings.location_id == location_id))
    if row is None:
        row = PilotSettings(organization_id=ctx.org_id, location_id=location_id)
        db.add(row)
    for field, value in data.model_dump().items():
        setattr(row, field, value)
    db.commit()
    return {"ok": True}


# ---------- локальная ЦА ----------


@router.get("/{location_id}/audience")
def list_audience(location_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ensure_location(db, ctx, location_id)
    rows = db.scalars(
        select(AudienceSegment)
        .where(AudienceSegment.location_id == location_id)
        .order_by(AudienceSegment.weekday, AudienceSegment.time_from)
    ).all()
    return [
        {
            "id": r.id,
            "weekday": r.weekday,
            "time_from": r.time_from,
            "time_to": r.time_to,
            "segment": r.segment,
            "age": r.age,
            "composition": r.composition,
            "behavior": r.behavior,
            "motive": r.motive,
            "what_works": r.what_works,
            "comment": r.comment,
        }
        for r in rows
    ]


@router.post("/{location_id}/audience")
def add_audience(location_id: int, data: AudienceIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    row = AudienceSegment(organization_id=ctx.org_id, location_id=location_id, **data.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.delete("/{location_id}/audience/{segment_id}")
def delete_audience(location_id: int, segment_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    row = db.get(AudienceSegment, segment_id)
    if not row or row.location_id != location_id:
        raise HTTPException(status_code=404, detail="Сегмент не найден")
    db.delete(row)
    db.commit()
    return {"ok": True}


# ---------- оценка точки ----------


@router.get("/{location_id}/score")
def get_score(location_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ensure_location(db, ctx, location_id)
    row = db.scalar(select(PointScore).where(PointScore.location_id == location_id))
    return {
        "location_id": location_id,
        "scores": row.scores if row else {},
        "index": row.index_value if row else 0.0,
        "interpretation": row.interpretation if row else "Заполните оценки",
        "parameters": [{"key": k, "label": v[0], "weight": v[1]} for k, v in SCORE_WEIGHTS.items()],
    }


@router.put("/{location_id}/score")
def put_score(location_id: int, data: ScoreIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    index, interpretation = _score_index(data.scores)
    row = db.scalar(select(PointScore).where(PointScore.location_id == location_id))
    if row is None:
        row = PointScore(organization_id=ctx.org_id, location_id=location_id)
        db.add(row)
    row.scores = data.scores
    row.index_value = index
    row.interpretation = interpretation
    db.commit()
    return {"index": index, "interpretation": interpretation}


# ---------- гипотезы ----------


@router.get("/{location_id}/hypotheses")
def list_hypotheses(location_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ensure_location(db, ctx, location_id)
    rows = db.scalars(
        select(Hypothesis).where(Hypothesis.location_id == location_id).order_by(Hypothesis.created_at)
    ).all()
    return [
        {
            "id": r.id,
            "hypothesis": r.hypothesis,
            "change": r.change,
            "metric": r.metric,
            "current_value": r.current_value,
            "expected_value": r.expected_value,
            "growth": r.growth,
            "test_days": r.test_days,
            "result": r.result,
            "conclusion": r.conclusion,
            "next_action": r.next_action,
        }
        for r in rows
    ]


@router.post("/{location_id}/hypotheses")
def add_hypothesis(location_id: int, data: HypothesisIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    row = Hypothesis(organization_id=ctx.org_id, location_id=location_id, **data.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.patch("/{location_id}/hypotheses/{hypothesis_id}")
def patch_hypothesis(
    location_id: int, hypothesis_id: int, body: dict, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)
):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    row = db.get(Hypothesis, hypothesis_id)
    if not row or row.location_id != location_id:
        raise HTTPException(status_code=404, detail="Гипотеза не найдена")
    for field in ("result", "conclusion", "next_action"):
        if field in body:
            setattr(row, field, body[field])
    db.commit()
    return {"ok": True}


# ---------- план тестов ----------


@router.get("/{location_id}/tests")
def list_tests(location_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ensure_location(db, ctx, location_id)
    rows = db.scalars(select(TestPlan).where(TestPlan.location_id == location_id).order_by(TestPlan.created_at)).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "what": r.what,
            "start_date": r.start_date.isoformat() if r.start_date else None,
            "end_date": r.end_date.isoformat() if r.end_date else None,
            "metric": r.metric,
            "goal": r.goal,
            "fact": r.fact,
            "result": r.result,
            "decision": r.decision,
        }
        for r in rows
    ]


@router.post("/{location_id}/tests")
def add_test(location_id: int, data: TestPlanIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    row = TestPlan(organization_id=ctx.org_id, location_id=location_id, **data.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.patch("/{location_id}/tests/{test_id}")
def patch_test(location_id: int, test_id: int, body: dict, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    row = db.get(TestPlan, test_id)
    if not row or row.location_id != location_id:
        raise HTTPException(status_code=404, detail="Тест не найден")
    for field in ("fact", "result", "decision"):
        if field in body:
            setattr(row, field, body[field])
    db.commit()
    return {"ok": True}


# ---------- тренды ----------


@router.get("/{location_id}/trends")
def list_trends(location_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ensure_location(db, ctx, location_id)
    rows = db.scalars(select(Trend).where(Trend.location_id == location_id).order_by(Trend.created_at.desc())).all()
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "title": r.title,
            "why": r.why,
            "idea": r.idea,
            "urgency": r.urgency,
            "effect": r.effect,
            "status": r.status,
        }
        for r in rows
    ]


@router.post("/{location_id}/trends")
def add_trend(location_id: int, data: TrendIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    row = Trend(organization_id=ctx.org_id, location_id=location_id, **data.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id}


# ---------- фото-аудит ----------


@router.get("/{location_id}/photos")
def list_photos(location_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ensure_location(db, ctx, location_id)
    rows = db.scalars(
        select(PhotoAudit).where(PhotoAudit.location_id == location_id).order_by(PhotoAudit.created_at.desc())
    ).all()
    return [
        {
            "id": r.id,
            "url": r.url,
            "angle": r.angle,
            "good": r.good,
            "bad": r.bad,
            "problem": r.problem,
            "recommendation": r.recommendation,
            "priority": r.priority,
        }
        for r in rows
    ]


@router.post("/{location_id}/photos")
def add_photo(location_id: int, data: PhotoAuditIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    row = PhotoAudit(organization_id=ctx.org_id, location_id=location_id, **data.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id}


# ---------- ручной ввод показателей ----------


@router.get("/{location_id}/manual")
def list_manual(
    location_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
    ctx: Ctx = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    ensure_location(db, ctx, location_id)
    today = date.today()
    to = date.fromisoformat(date_to) if date_to else today
    frm = date.fromisoformat(date_from) if date_from else to - timedelta(days=59)
    rows = db.scalars(
        select(ManualDailyMetric)
        .where(
            ManualDailyMetric.location_id == location_id,
            ManualDailyMetric.day >= datetime.combine(frm, datetime.min.time()),
            ManualDailyMetric.day < datetime.combine(to + timedelta(days=1), datetime.min.time()),
        )
        .order_by(ManualDailyMetric.day.desc())
    ).all()
    return [
        {
            "id": r.id,
            "day": r.day.date().isoformat(),
            "revenue": r.revenue,
            "receipts": r.receipts,
            "entries": r.entries,
            "looked": r.looked,
            "passersby": r.passersby,
            "avg_check": round(r.revenue / r.receipts, 2) if r.revenue and r.receipts else None,
            "note": r.note,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


@router.post("/{location_id}/manual")
def upsert_manual(location_id: int, data: ManualMetricIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    day = datetime.combine(data.day, datetime.min.time())
    row = db.scalar(
        select(ManualDailyMetric).where(
            ManualDailyMetric.location_id == location_id, ManualDailyMetric.day == day
        )
    )
    if row is None:
        row = ManualDailyMetric(organization_id=ctx.org_id, location_id=location_id, day=day)
        db.add(row)
    row.revenue = data.revenue
    row.receipts = data.receipts
    row.entries = data.entries
    row.looked = data.looked
    row.passersby = data.passersby
    row.note = data.note
    row.created_by = ctx.user.id
    db.commit()
    return {"ok": True, "day": data.day.isoformat()}


@router.delete("/{location_id}/manual/{day}")
def delete_manual(location_id: int, day: str, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, location_id)
    moment = datetime.combine(date.fromisoformat(day), datetime.min.time())
    row = db.scalar(
        select(ManualDailyMetric).where(
            ManualDailyMetric.location_id == location_id, ManualDailyMetric.day == moment
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    db.delete(row)
    db.commit()
    return {"ok": True}
