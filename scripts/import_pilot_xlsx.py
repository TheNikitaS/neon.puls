"""Импорт пилотной книги (пример: Subjoy.xlsx) в платформу.

Структура книги используется как шаблон: настройки пилота, данные по дням,
локальная ЦА, гипотезы, план тестов, тренды, фото-аудит, оценка точки,
рекомендации. Значения из файла — демонстрационные.

Запуск:
    python scripts/import_pilot_xlsx.py "D:\\Неон.Пульс\\Subjoy.xlsx"
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl
from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.migrations import ensure_columns  # noqa: E402
from app.models import (  # noqa: E402
    AttentionMetric,
    AudienceSegment,
    Hypothesis,
    Location,
    Organization,
    PhotoAudit,
    PilotSettings,
    PointScore,
    Recommendation,
    TestPlan,
    Transaction,
    Trend,
    VisitorMetric,
)

SCORE_KEYS = {
    "Видимость с расстояния": "visibility",
    "Читаемость вывески": "readability",
    "Контраст с окружением": "contrast",
    "Световой объём": "light",
    "Понятность входа": "entrance",
    "Импульсность": "impulse",
    "Фото/видео привлекательность": "photo",
    "Соответствие ЦА": "audience",
    "Сезонность": "season",
    "Потенциал масштабирования": "scale",
}

SCORE_WEIGHTS = {
    "visibility": 1.2,
    "readability": 1.1,
    "contrast": 1.0,
    "light": 1.0,
    "entrance": 1.0,
    "impulse": 0.9,
    "photo": 0.7,
    "audience": 1.0,
    "season": 0.6,
    "scale": 0.8,
}


def text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value).strip()


def number(value) -> float | None:
    if value is None or isinstance(value, str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sheet_rows(ws, start_row: int, columns: dict[str, str]) -> list[dict]:
    rows = []
    for row in ws.iter_rows(min_row=start_row, max_row=ws.max_row):
        item = {}
        for key, col in columns.items():
            item[key] = row[openpyxl.utils.column_index_from_string(col) - 1].value
        if any(v not in (None, "") for v in item.values()):
            rows.append(item)
    return rows


def main(path: str) -> int:
    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)
    wb = openpyxl.load_workbook(path, data_only=False)
    db = SessionLocal()
    try:
        org = db.scalar(select(Organization).order_by(Organization.id))
        if org is None:
            org = Organization(name="Демо-компания", slug="demo", industry="retail")
            db.add(org)
            db.flush()

        settings_ws = wb["Настройки"]
        point_name = text(settings_ws["B11"].value) or "SUBJOY"
        address = text(settings_ws["B12"].value)
        signage = settings_ws["B4"].value
        camera = settings_ws["B5"].value
        avg_check = number(settings_ws["B7"].value) or 450.0
        target = number(settings_ws["B8"].value) or 0.3
        min_before = int(number(settings_ws["B9"].value) or 30)
        min_after = int(number(settings_ws["B10"].value) or 30)

        loc = db.scalar(
            select(Location).where(Location.organization_id == org.id, Location.name == point_name)
        )
        if loc is None:
            loc = Location(
                organization_id=org.id,
                name=point_name,
                address=address,
                city="",
                status="active",
                attention_enabled=True,
            )
            db.add(loc)
            db.flush()
        else:
            loc.address = address or loc.address

        # Чистим предыдущий импорт этой точки
        for model in (AttentionMetric, VisitorMetric, Transaction):
            db.execute(delete(model).where(model.location_id == loc.id))
        for model in (AudienceSegment, Hypothesis, TestPlan, Trend, PhotoAudit):
            db.execute(delete(model).where(model.location_id == loc.id))
        db.execute(delete(Recommendation).where(Recommendation.location_id == loc.id))
        db.execute(delete(PointScore).where(PointScore.location_id == loc.id))
        db.execute(delete(PilotSettings).where(PilotSettings.location_id == loc.id))

        db.add(
            PilotSettings(
                organization_id=org.id,
                location_id=loc.id,
                signage_date=signage if isinstance(signage, datetime) else None,
                camera_date=camera if isinstance(camera, datetime) else None,
                compare_days=int(number(settings_ws["B6"].value) or 60),
                avg_check=avg_check,
                target_growth=target,
                min_days_before=min_before,
                min_days_after=min_after,
                point_name=point_name,
                address=address,
                comment=text(settings_ws["B13"].value),
            )
        )

        # Данные по дням
        daily = wb["Данные по дням"]
        imported_days = 0
        for row in daily.iter_rows(min_row=2, max_row=daily.max_row):
            day = row[0].value
            if not isinstance(day, datetime):
                continue
            checks = number(row[3].value)
            looks = number(row[4].value)
            entries = number(row[5].value)
            if not any(v for v in (checks, looks, entries)):
                continue
            imported_days += 1
            if looks:
                db.add(
                    AttentionMetric(
                        organization_id=org.id,
                        location_id=loc.id,
                        ts=day,
                        passersby=int(looks * 4),
                        looked=int(looks),
                        approached=int(looks * 0.4),
                        source="pilot_import",
                    )
                )
            if entries:
                db.add(
                    VisitorMetric(
                        organization_id=org.id,
                        location_id=loc.id,
                        ts=day.replace(hour=12),
                        entries=int(entries),
                        unique_visitors=int(entries * 0.93),
                        dwell_avg_sec=240.0,
                        source="pilot_import",
                    )
                )
            if checks:
                for n in range(int(checks)):
                    db.add(
                        Transaction(
                            organization_id=org.id,
                            location_id=loc.id,
                            ts=day.replace(hour=12, minute=min(n, 59)),
                            receipt_no=f"pilot-{day.strftime('%Y%m%d')}-{n:03d}",
                            amount=avg_check,
                            items_count=1,
                            is_return=False,
                            source="pilot_import",
                        )
                    )

        # ЦА и трафик
        audience_ws = wb["ЦА и трафик"]
        for row in sheet_rows(
            audience_ws,
            4,
            {
                "weekday": "B",
                "time": "C",
                "segment": "D",
                "age": "E",
                "composition": "F",
                "behavior": "G",
                "motive": "H",
                "what_works": "I",
                "comment": "J",
            },
        ):
            if not text(row["segment"]):
                continue
            window = text(row["time"]).replace("–", "-").split("-")
            db.add(
                AudienceSegment(
                    organization_id=org.id,
                    location_id=loc.id,
                    weekday=text(row["weekday"]) or "Ежедневно",
                    time_from=window[0].strip() if len(window) > 0 else "",
                    time_to=window[1].strip() if len(window) > 1 else "",
                    segment=text(row["segment"]),
                    age=text(row["age"]),
                    composition=text(row["composition"]),
                    behavior=text(row["behavior"]),
                    motive=text(row["motive"]),
                    what_works=text(row["what_works"]),
                    comment=text(row["comment"]),
                )
            )

        # Гипотезы
        hyp_ws = wb["Гипотезы"]
        for row in sheet_rows(
            hyp_ws,
            4,
            {
                "hypothesis": "A",
                "change": "B",
                "metric": "C",
                "current": "D",
                "expected": "E",
                "growth": "F",
                "days": "G",
                "result": "H",
                "conclusion": "I",
                "next": "J",
            },
        ):
            if not text(row["hypothesis"]):
                continue
            db.add(
                Hypothesis(
                    organization_id=org.id,
                    location_id=loc.id,
                    hypothesis=text(row["hypothesis"]),
                    change=text(row["change"]),
                    metric=text(row["metric"]),
                    current_value=text(row["current"]),
                    expected_value=text(row["expected"]),
                    growth=text(row["growth"]),
                    test_days=text(row["days"]),
                    result=text(row["result"]) or "Не начато",
                    conclusion=text(row["conclusion"]),
                    next_action=text(row["next"]),
                )
            )

        # План тестов
        tests_ws = wb["План тестов"]
        for row in sheet_rows(
            tests_ws,
            4,
            {
                "name": "B",
                "what": "C",
                "start": "D",
                "end": "E",
                "metric": "F",
                "goal": "G",
                "fact": "H",
                "result": "I",
                "decision": "J",
            },
        ):
            if not text(row["name"]):
                continue
            db.add(
                TestPlan(
                    organization_id=org.id,
                    location_id=loc.id,
                    name=text(row["name"]),
                    what=text(row["what"]),
                    start_date=row["start"] if isinstance(row["start"], datetime) else None,
                    end_date=row["end"] if isinstance(row["end"], datetime) else None,
                    metric=text(row["metric"]),
                    goal=text(row["goal"]),
                    fact=text(row["fact"]),
                    result=text(row["result"]) or "Не начато",
                    decision=text(row["decision"]),
                )
            )

        # Тренды
        trends_ws = wb["Тренды"]
        for row in sheet_rows(
            trends_ws,
            4,
            {"kind": "B", "title": "C", "why": "D", "idea": "E", "urgency": "F", "effect": "G", "status": "H"},
        ):
            if not text(row["title"]):
                continue
            db.add(
                Trend(
                    organization_id=org.id,
                    location_id=loc.id,
                    kind=text(row["kind"]),
                    title=text(row["title"]),
                    why=text(row["why"]),
                    idea=text(row["idea"]),
                    urgency=text(row["urgency"]),
                    effect=text(row["effect"]),
                    status=text(row["status"]) or "Идея",
                )
            )

        # Фото-аудит
        photos_ws = wb["Фото аудит"]
        for row in sheet_rows(
            photos_ws,
            4,
            {"angle": "C", "good": "D", "bad": "E", "problem": "F", "recommendation": "G", "priority": "H"},
        ):
            if not text(row["angle"]):
                continue
            db.add(
                PhotoAudit(
                    organization_id=org.id,
                    location_id=loc.id,
                    angle=text(row["angle"]),
                    good=text(row["good"]),
                    bad=text(row["bad"]),
                    problem=text(row["problem"]),
                    recommendation=text(row["recommendation"]),
                    priority=text(row["priority"]) or "Средний",
                )
            )

        # Оценка точки
        score_ws = wb["Оценка точки"]
        scores: dict[str, int] = {}
        for row in score_ws.iter_rows(min_row=4, max_row=13):
            label = text(row[0].value)
            value = number(row[1].value)
            key = SCORE_KEYS.get(label)
            if key and value:
                scores[key] = int(value)
        if scores:
            total = sum(scores[k] * SCORE_WEIGHTS[k] for k in scores)
            weight = sum(SCORE_WEIGHTS[k] for k in scores)
            index = round(total / weight, 2) if weight else 0.0
            if index < 2.5:
                interpretation = "Точка визуально слабая"
            elif index < 3.5:
                interpretation = "Есть база, но много потерь"
            elif index < 4.3:
                interpretation = "Хорошая точка, можно усиливать"
            else:
                interpretation = "Сильная точка, задача — оптимизация и тесты"
            db.add(
                PointScore(
                    organization_id=org.id,
                    location_id=loc.id,
                    scores=scores,
                    index_value=index,
                    interpretation=interpretation,
                )
            )

        # Рекомендации
        rec_ws = wb["Рекомендации"]
        for row in sheet_rows(
            rec_ws,
            4,
            {
                "priority": "A",
                "zone": "B",
                "what": "C",
                "why": "D",
                "effect": "E",
                "complexity": "F",
                "budget": "G",
                "growth": "H",
                "status": "I",
                "comment": "J",
            },
        ):
            if not text(row["what"]):
                continue
            db.add(
                Recommendation(
                    organization_id=org.id,
                    location_id=loc.id,
                    title=text(row["what"]),
                    rationale=text(row["why"]),
                    actions=[text(row["what"])],
                    expected_effect=text(row["effect"]),
                    measurement_plan="Сравнить показатели до/после с учётом дня недели и времени.",
                    status="new",
                    result={
                        "priority": text(row["priority"]),
                        "zone": text(row["zone"]),
                        "complexity": text(row["complexity"]),
                        "budget": text(row["budget"]),
                        "growth_potential": text(row["growth"]),
                        "comment": text(row["comment"]),
                    },
                )
            )

        db.commit()
        print(f"Импорт завершён: точка «{loc.name}», дней с данными {imported_days}, сегментов ЦА {len(scores) and 'ок'}")
        print(f"  гипотезы, тесты, тренды, фото-аудит, оценка и рекомендации загружены")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "Subjoy.xlsx"
    sys.exit(main(target))
