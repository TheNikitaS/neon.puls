"""Аналитическое ядро: KPI, динамика, сравнение точек, «до/после».

Все расчёты идут по нормализованным данным (attention_metrics, visitor_metrics,
transactions) и всегда ограничены организацией и доступными точками.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AttentionMetric, Location, ManualDailyMetric, Transaction, VisitorMetric


def _safe_div(a: float, b: float) -> float:
    return round(a / b, 4) if b else 0.0


def load_rows(db: Session, org_id: int, location_ids: list[int], date_from: date, date_to: date):
    if not location_ids:
        return [], [], []
    start = datetime.combine(date_from, datetime.min.time())
    end = datetime.combine(date_to + timedelta(days=1), datetime.min.time())
    att = db.scalars(
        select(AttentionMetric).where(
            AttentionMetric.organization_id == org_id,
            AttentionMetric.location_id.in_(location_ids),
            AttentionMetric.ts >= start,
            AttentionMetric.ts < end,
        )
    ).all()
    vis = db.scalars(
        select(VisitorMetric).where(
            VisitorMetric.organization_id == org_id,
            VisitorMetric.location_id.in_(location_ids),
            VisitorMetric.ts >= start,
            VisitorMetric.ts < end,
        )
    ).all()
    tx = db.scalars(
        select(Transaction).where(
            Transaction.organization_id == org_id,
            Transaction.location_id.in_(location_ids),
            Transaction.ts >= start,
            Transaction.ts < end,
        )
    ).all()
    return att, vis, tx


def daily_series(db: Session, org_id: int, location_ids: list[int], date_from: date, date_to: date) -> list[dict]:
    att, vis, tx = load_rows(db, org_id, location_ids, date_from, date_to)
    buckets: dict[tuple[int, date], dict] = {}

    def bucket(loc_id: int, day: date) -> dict:
        key = (loc_id, day)
        if key not in buckets:
            buckets[key] = {
                "passersby": 0,
                "looked": 0,
                "approached": 0,
                "entries": 0,
                "unique_visitors": 0,
                "dwell_sec": 0.0,
                "dwell_n": 0,
                "receipts": 0,
                "revenue": 0.0,
                "returns": 0.0,
                "manual": False,
            }
        return buckets[key]

    for row in att:
        b = bucket(row.location_id, row.ts.date())
        b["passersby"] += row.passersby
        b["looked"] += row.looked
        b["approached"] += row.approached
    for row in vis:
        b = bucket(row.location_id, row.ts.date())
        b["entries"] += row.entries
        b["unique_visitors"] += row.unique_visitors
        if row.dwell_avg_sec:
            b["dwell_sec"] += row.dwell_avg_sec
            b["dwell_n"] += 1
    for row in tx:
        b = bucket(row.location_id, row.ts.date())
        if row.is_return:
            b["returns"] += abs(row.amount)
        else:
            b["receipts"] += 1
            b["revenue"] += row.amount

    # Ручной ввод перекрывает данные API за этот день по этой точке
    if location_ids:
        manual_rows = db.scalars(
            select(ManualDailyMetric).where(
                ManualDailyMetric.organization_id == org_id,
                ManualDailyMetric.location_id.in_(location_ids),
                ManualDailyMetric.day >= datetime.combine(date_from, datetime.min.time()),
                ManualDailyMetric.day < datetime.combine(date_to + timedelta(days=1), datetime.min.time()),
            )
        ).all()
        for row in manual_rows:
            b = bucket(row.location_id, row.day.date())
            if row.revenue is not None:
                b["revenue"] = row.revenue
                b["returns"] = 0.0
            if row.receipts is not None:
                b["receipts"] = row.receipts
            if row.entries is not None:
                b["entries"] = row.entries
            if row.looked is not None:
                b["looked"] = row.looked
            if row.passersby is not None:
                b["passersby"] = row.passersby
            b["manual"] = True

    days: dict[date, dict] = {}
    cursor = date_from
    while cursor <= date_to:
        days[cursor] = {
            "date": cursor.isoformat(),
            "passersby": 0,
            "looked": 0,
            "approached": 0,
            "entries": 0,
            "unique_visitors": 0,
            "dwell_sec": 0.0,
            "dwell_n": 0,
            "receipts": 0,
            "revenue": 0.0,
            "returns": 0.0,
            "manual": False,
        }
        cursor += timedelta(days=1)

    for (_loc_id, day), b in buckets.items():
        target = days.get(day)
        if target is None:
            continue
        for field in ("passersby", "looked", "approached", "entries", "unique_visitors", "receipts", "revenue", "returns", "dwell_sec", "dwell_n"):
            target[field] += b[field]
        target["manual"] = target["manual"] or b["manual"]

    out = []
    for day in sorted(days):
        b = days[day]
        revenue = round(b["revenue"] - b["returns"], 2)
        out.append(
            {
                "date": b["date"],
                "passersby": b["passersby"],
                "looked": b["looked"],
                "approached": b["approached"],
                "entries": b["entries"],
                "unique_visitors": b["unique_visitors"],
                "dwell_avg_sec": round(b["dwell_sec"] / b["dwell_n"], 1) if b["dwell_n"] else 0,
                "receipts": b["receipts"],
                "revenue": revenue,
                "avg_check": round(revenue / b["receipts"], 2) if b["receipts"] else 0,
                "attention_rate": _safe_div(b["looked"], b["passersby"]),
                "entry_conversion": _safe_div(b["entries"], b["passersby"]),
                "purchase_conversion": _safe_div(b["receipts"], b["entries"]),
                "manual": b["manual"],
            }
        )
    return out


def totals(series: list[dict]) -> dict:
    agg = {
        "passersby": 0,
        "looked": 0,
        "approached": 0,
        "entries": 0,
        "unique_visitors": 0,
        "receipts": 0,
        "revenue": 0.0,
        "dwell_sec": 0.0,
        "dwell_n": 0,
    }
    for row in series:
        agg["passersby"] += row["passersby"]
        agg["looked"] += row["looked"]
        agg["approached"] += row["approached"]
        agg["entries"] += row["entries"]
        agg["unique_visitors"] += row["unique_visitors"]
        agg["receipts"] += row["receipts"]
        agg["revenue"] += row["revenue"]
        if row["dwell_avg_sec"]:
            agg["dwell_sec"] += row["dwell_avg_sec"]
            agg["dwell_n"] += 1
    revenue = round(agg["revenue"], 2)
    return {
        "passersby": agg["passersby"],
        "looked": agg["looked"],
        "approached": agg["approached"],
        "entries": agg["entries"],
        "unique_visitors": agg["unique_visitors"],
        "receipts": agg["receipts"],
        "revenue": revenue,
        "avg_check": round(revenue / agg["receipts"], 2) if agg["receipts"] else 0,
        "attention_rate": _safe_div(agg["looked"], agg["passersby"]),
        "entry_conversion": _safe_div(agg["entries"], agg["passersby"]),
        "purchase_conversion": _safe_div(agg["receipts"], agg["entries"]),
        "revenue_per_visitor": round(revenue / agg["entries"], 2) if agg["entries"] else 0,
        "dwell_avg_sec": round(agg["dwell_sec"] / agg["dwell_n"], 1) if agg["dwell_n"] else 0,
        "days": len(series),
    }


def delta(current: float, previous: float) -> dict:
    if not previous:
        return {"abs": round(current - previous, 2), "pct": None}
    return {"abs": round(current - previous, 2), "pct": round((current - previous) / previous * 100, 1)}


def compare_periods(db: Session, org_id: int, location_ids: list[int], date_from: date, date_to: date) -> dict:
    span = (date_to - date_from).days + 1
    prev_to = date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=span - 1)
    cur = totals(daily_series(db, org_id, location_ids, date_from, date_to))
    prev = totals(daily_series(db, org_id, location_ids, prev_from, prev_to))
    keys = [
        "passersby",
        "looked",
        "entries",
        "receipts",
        "revenue",
        "avg_check",
        "attention_rate",
        "entry_conversion",
        "purchase_conversion",
        "revenue_per_visitor",
    ]
    return {
        "period": {"from": date_from.isoformat(), "to": date_to.isoformat(), "days": span},
        "previous_period": {"from": prev_from.isoformat(), "to": prev_to.isoformat()},
        "current": cur,
        "previous": prev,
        "delta": {key: delta(cur[key], prev[key]) for key in keys},
    }


def hourly_profile(db: Session, org_id: int, location_ids: list[int], date_from: date, date_to: date) -> list[dict]:
    _att, vis, tx = load_rows(db, org_id, location_ids, date_from, date_to)
    hours = {h: {"hour": h, "entries": 0, "receipts": 0, "revenue": 0.0} for h in range(24)}
    for row in vis:
        hours[row.ts.hour]["entries"] += row.entries
    for row in tx:
        if row.is_return:
            continue
        hours[row.ts.hour]["receipts"] += 1
        hours[row.ts.hour]["revenue"] += row.amount
    return [
        {
            "hour": h,
            "entries": v["entries"],
            "receipts": v["receipts"],
            "revenue": round(v["revenue"], 2),
            "conversion": _safe_div(v["receipts"], v["entries"]),
        }
        for h, v in hours.items()
    ]


def weekday_profile(db: Session, org_id: int, location_ids: list[int], date_from: date, date_to: date) -> list[dict]:
    series = daily_series(db, org_id, location_ids, date_from, date_to)
    names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    buckets = {i: {"weekday": names[i], "entries": 0, "receipts": 0, "revenue": 0.0, "days": 0} for i in range(7)}
    for row in series:
        idx = datetime.fromisoformat(row["date"]).weekday()
        b = buckets[idx]
        b["entries"] += row["entries"]
        b["receipts"] += row["receipts"]
        b["revenue"] += row["revenue"]
        b["days"] += 1
    out = []
    for i in range(7):
        b = buckets[i]
        n = max(b["days"], 1)
        out.append(
            {
                "weekday": b["weekday"],
                "entries": round(b["entries"] / n),
                "receipts": round(b["receipts"] / n),
                "revenue": round(b["revenue"] / n, 2),
                "conversion": _safe_div(b["receipts"], b["entries"]),
            }
        )
    return out


def location_ranking(db: Session, org_id: int, location_ids: list[int], date_from: date, date_to: date) -> list[dict]:
    if not location_ids:
        return []
    locations = {loc.id: loc for loc in db.scalars(select(Location).where(Location.id.in_(location_ids))).all()}
    rows = []
    for loc_id in location_ids:
        series = daily_series(db, org_id, [loc_id], date_from, date_to)
        t = totals(series)
        loc = locations.get(loc_id)
        rows.append(
            {
                "location_id": loc_id,
                "name": loc.name if loc else f"Точка {loc_id}",
                "city": loc.city if loc else "",
                "status": loc.status if loc else "",
                **{
                    k: t[k]
                    for k in (
                        "passersby",
                        "entries",
                        "receipts",
                        "revenue",
                        "avg_check",
                        "entry_conversion",
                        "purchase_conversion",
                        "attention_rate",
                    )
                },
            }
        )
    rows.sort(key=lambda r: r["revenue"], reverse=True)
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def before_after(
    db: Session,
    org_id: int,
    location_id: int,
    change_at: datetime,
    baseline_days: int = 14,
    result_days: int = 14,
) -> dict:
    change_day = change_at.date()
    base_to = change_day - timedelta(days=1)
    base_from = base_to - timedelta(days=baseline_days - 1)
    res_from = change_day
    res_to = change_day + timedelta(days=result_days - 1)
    base = totals(daily_series(db, org_id, [location_id], base_from, base_to))
    res = totals(daily_series(db, org_id, [location_id], res_from, res_to))
    keys = [
        "passersby",
        "entries",
        "receipts",
        "revenue",
        "avg_check",
        "entry_conversion",
        "purchase_conversion",
        "attention_rate",
    ]
    return {
        "location_id": location_id,
        "change_at": change_at.isoformat(),
        "baseline": {"from": base_from.isoformat(), "to": base_to.isoformat(), "metrics": base},
        "result": {"from": res_from.isoformat(), "to": res_to.isoformat(), "metrics": res},
        "delta": {key: delta(res[key], base[key]) for key in keys},
    }


def anomalies(db: Session, org_id: int, location_ids: list[int], lookback_days: int = 21) -> list[dict]:
    """Z-score по дневной выручке и входам относительно предыдущих дней."""
    today = date.today()
    series = daily_series(db, org_id, location_ids, today - timedelta(days=lookback_days), today)
    if len(series) < 8:
        return []
    found = []
    for metric in ("revenue", "entries"):
        values = [row[metric] for row in series]
        history = values[:-1]
        mean = sum(history) / len(history)
        var = sum((v - mean) ** 2 for v in history) / max(len(history) - 1, 1)
        std = var ** 0.5
        last = values[-1]
        if std <= 0:
            continue
        z = (last - mean) / std
        if abs(z) >= 2.0:
            found.append(
                {
                    "metric": metric,
                    "value": last,
                    "mean": round(mean, 2),
                    "z_score": round(z, 2),
                    "direction": "up" if z > 0 else "down",
                    "date": series[-1]["date"],
                }
            )
    return found
