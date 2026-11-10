"""AI-аналитик: разбор точки, сети, вопросы, рекомендации, эксперименты."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Ctx, accessible_location_ids, ensure_location, get_ctx
from ..models import AiInsight, Change, Experiment, Location, Recommendation
from ..schemas import AskIn, ExperimentIn, RecommendationPatch
from ..services import ai_engine, analytics

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/analyze/{location_id}")
def analyze(location_id: int, days: int = 28, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ensure_location(db, ctx, location_id)
    insights = ai_engine.analyze_location(db, ctx.org_id, location_id, days)
    saved = ai_engine.persist(db, ctx.org_id, location_id, insights)
    return {
        "location_id": location_id,
        "insights": [
            {
                "id": row.id,
                "kind": row.kind,
                "severity": row.severity,
                "title": row.title,
                "summary": row.summary,
                "evidence": row.evidence,
                "confidence": row.confidence,
                "limitations": row.limitations,
                "period_from": row.period_from.isoformat() if row.period_from else None,
                "period_to": row.period_to.isoformat() if row.period_to else None,
                "recommendation": ai_engine.recommendation_for(
                    {"kind": row.kind, "summary": row.summary}
                ),
            }
            for row in saved
        ],
    }


@router.post("/analyze-network")
def analyze_network(days: int = 28, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ids = accessible_location_ids(db, ctx)
    insights = ai_engine.analyze_network(db, ctx.org_id, ids, days)
    saved = ai_engine.persist(db, ctx.org_id, None, insights)
    return {
        "insights": [
            {
                "id": row.id,
                "kind": row.kind,
                "severity": row.severity,
                "title": row.title,
                "summary": row.summary,
                "evidence": row.evidence,
                "confidence": row.confidence,
                "limitations": row.limitations,
                "recommendation": ai_engine.recommendation_for({"kind": row.kind, "summary": row.summary}),
            }
            for row in saved
        ]
    }


@router.get("/insights")
def insights(
    location_id: int | None = None,
    limit: int = 30,
    ctx: Ctx = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    ids = accessible_location_ids(db, ctx)
    stmt = select(AiInsight).where(AiInsight.organization_id == ctx.org_id)
    if location_id:
        ensure_location(db, ctx, location_id)
        stmt = stmt.where(AiInsight.location_id == location_id)
    else:
        stmt = stmt.where((AiInsight.location_id.is_(None)) | (AiInsight.location_id.in_(ids)))
    rows = db.scalars(stmt.order_by(AiInsight.created_at.desc()).limit(limit)).all()
    names = {loc.id: loc.name for loc in db.scalars(select(Location).where(Location.id.in_(ids))).all()}
    return [
        {
            "id": r.id,
            "location_id": r.location_id,
            "location": names.get(r.location_id, "Сеть"),
            "kind": r.kind,
            "severity": r.severity,
            "title": r.title,
            "summary": r.summary,
            "evidence": r.evidence,
            "confidence": r.confidence,
            "limitations": r.limitations,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/recommendations")
def recommendations(
    location_id: int | None = None,
    status: str | None = None,
    ctx: Ctx = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    ids = accessible_location_ids(db, ctx)
    stmt = select(Recommendation).where(Recommendation.organization_id == ctx.org_id)
    if location_id:
        ensure_location(db, ctx, location_id)
        stmt = stmt.where(Recommendation.location_id == location_id)
    else:
        stmt = stmt.where((Recommendation.location_id.is_(None)) | (Recommendation.location_id.in_(ids)))
    if status:
        stmt = stmt.where(Recommendation.status == status)
    rows = db.scalars(stmt.order_by(Recommendation.created_at.desc()).limit(100)).all()
    names = {loc.id: loc.name for loc in db.scalars(select(Location).where(Location.id.in_(ids))).all()}
    return [
        {
            "id": r.id,
            "location_id": r.location_id,
            "location": names.get(r.location_id, "Сеть"),
            "title": r.title,
            "rationale": r.rationale,
            "actions": r.actions,
            "expected_effect": r.expected_effect,
            "measurement_plan": r.measurement_plan,
            "status": r.status,
            "result": r.result,
            "effectiveness_score": r.effectiveness_score,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.patch("/recommendations/{rec_id}")
def patch_recommendation(rec_id: int, data: RecommendationPatch, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    rec = db.get(Recommendation, rec_id)
    if not rec or rec.organization_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Рекомендация не найдена")
    rec.status = data.status
    db.commit()
    return {"ok": True, "status": rec.status}


@router.post("/ask")
def ask(data: AskIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ids = accessible_location_ids(db, ctx)
    if data.location_id:
        ensure_location(db, ctx, data.location_id)
    return ai_engine.answer_question(db, ctx.org_id, ids, data.question, data.location_id)


@router.post("/experiments")
def create_experiment(data: ExperimentIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ctx.require("LOCATION_MANAGER")
    ensure_location(db, ctx, data.location_id)
    if data.change_id:
        change = db.get(Change, data.change_id)
        if not change or change.location_id != data.location_id:
            raise HTTPException(status_code=404, detail="Изменение не найдено")
        moment = change.applied_at
    else:
        moment = datetime.utcnow()
    base_to = moment - timedelta(days=1)
    base_from = base_to - timedelta(days=data.baseline_days - 1)
    res_from = moment
    res_to = moment + timedelta(days=data.result_days - 1)
    result = analytics.before_after(db, ctx.org_id, data.location_id, moment, data.baseline_days, data.result_days)
    verdict = "inconclusive"
    rev = result["delta"]["revenue"]["pct"]
    conv = result["delta"]["entry_conversion"]["pct"]
    if rev is not None and rev >= 5:
        verdict = "improved"
    elif rev is not None and rev <= -5:
        verdict = "worse"
    elif rev is not None:
        verdict = "no_change"
    exp = Experiment(
        organization_id=ctx.org_id,
        location_id=data.location_id,
        recommendation_id=data.recommendation_id,
        change_id=data.change_id,
        title=data.title,
        baseline_from=base_from,
        baseline_to=base_to,
        result_from=res_from,
        result_to=res_to,
        status="finished" if res_to <= datetime.utcnow() else "running",
        verdict=verdict,
        metrics=result,
    )
    db.add(exp)
    if data.recommendation_id:
        rec = db.get(Recommendation, data.recommendation_id)
        if rec and rec.organization_id == ctx.org_id:
            rec.status = "done"
            rec.result = result["delta"]
            rec.effectiveness_score = rev
    db.commit()
    return {"id": exp.id, "verdict": verdict, "metrics": result}


@router.get("/experiments")
def list_experiments(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    ids = accessible_location_ids(db, ctx)
    rows = db.scalars(
        select(Experiment)
        .where(Experiment.organization_id == ctx.org_id, Experiment.location_id.in_(ids))
        .order_by(Experiment.created_at.desc())
    ).all()
    names = {loc.id: loc.name for loc in db.scalars(select(Location).where(Location.id.in_(ids))).all()}
    return [
        {
            "id": r.id,
            "location_id": r.location_id,
            "location": names.get(r.location_id, ""),
            "title": r.title,
            "status": r.status,
            "verdict": r.verdict,
            "baseline": {"from": r.baseline_from.isoformat(), "to": r.baseline_to.isoformat()},
            "result": {"from": r.result_from.isoformat(), "to": r.result_to.isoformat()},
            "metrics": r.metrics,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
