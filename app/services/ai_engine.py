"""AI-аналитик НЕОН.ПУЛЬС.

Ядро детерминированное: считает факты по данным, формулирует вывод, показывает
доказательства, уверенность и ограничения. Провайдер LLM подключается отдельным
адаптером и не меняет расчётную часть — он только переформулирует текст.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import LLM_PROVIDER
from ..models import AiInsight, AudienceSegment, Location, Recommendation
from . import analytics
from . import llm

LIMITATIONS_BASE = [
    "Данные агрегированы по зонам и часам: персональная атрибуция «этот посетитель совершил эту покупку» не выполняется.",
    "Видеоаналитика измеряет вход и внимание с погрешностью, зависящей от ракурса камеры и освещения.",
    "Внешние факторы (погода, городские события, акции конкурентов) в модели не учтены.",
]


def _pct(cur: float, prev: float) -> float | None:
    if not prev:
        return None
    return round((cur - prev) / prev * 100, 1)


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "н/д"
    return f"{value:+.1f}%".replace(".", ",")


def _n(value: float) -> str:
    """Число с пробелами между разрядами: 15 743 833."""
    return f"{value:,.0f}".replace(",", " ")


def _audience_context(db: Session, location: Location) -> dict:
    """Локальный контекст точки: адрес, район и описанные сегменты ЦА."""
    segments = db.scalars(
        select(AudienceSegment)
        .where(AudienceSegment.location_id == location.id)
        .order_by(AudienceSegment.weekday, AudienceSegment.time_from)
    ).all()
    return {
        "location": location.name,
        "address": location.address,
        "city": location.city,
        "district": location.district,
        "note": location.audience_note,
        "segments": [
            {
                "weekday": s.weekday,
                "time_from": s.time_from,
                "time_to": s.time_to,
                "segment": s.segment,
                "age": s.age,
                "composition": s.composition,
                "behavior": s.behavior,
                "motive": s.motive,
                "what_works": s.what_works,
            }
            for s in segments
        ],
    }


def _place(location: Location) -> str:
    parts = [location.name]
    if location.address:
        parts.append(location.address)
    if location.district:
        parts.append(f"район {location.district}")
    elif location.city:
        parts.append(location.city)
    return " · ".join(parts)


def _minutes(value: str) -> int | None:
    try:
        hours, minutes = value.split(":")[:2]
        return int(hours) * 60 + int(minutes)
    except Exception:
        return None


def _confidence(days: int, magnitude: float) -> float:
    base = 0.45 + min(days, 60) / 60 * 0.25
    base += min(abs(magnitude), 40) / 40 * 0.2
    return round(min(base, 0.92), 2)


def _insight(
    kind: str,
    severity: str,
    title: str,
    summary: str,
    evidence: dict,
    confidence: float,
    period_from: date,
    period_to: date,
    limitations: list[str] | None = None,
) -> dict:
    return {
        "kind": kind,
        "severity": severity,
        "title": title,
        "summary": summary,
        "evidence": evidence,
        "confidence": confidence,
        "limitations": (limitations or []) + LIMITATIONS_BASE,
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
    }


def analyze_location(db: Session, org_id: int, location_id: int, days: int = 28) -> list[dict]:
    """Полный разбор одной точки: динамика, конверсии, внимание, аномалии."""
    loc = db.get(Location, location_id)
    if not loc:
        return []
    audience = _audience_context(db, loc)
    place = _place(loc)
    today = date.today()
    date_to = today - timedelta(days=1)
    date_from = date_to - timedelta(days=days - 1)
    cmp = analytics.compare_periods(db, org_id, [location_id], date_from, date_to)
    cur, prev, d = cmp["current"], cmp["previous"], cmp["delta"]
    out: list[dict] = []
    name = place

    traffic_pct = d["passersby"]["pct"]
    entries_pct = d["entries"]["pct"]
    conv_pct = d["entry_conversion"]["pct"]

    if traffic_pct is not None and entries_pct is not None and traffic_pct >= 8 and abs(entries_pct) < 4:
        out.append(
            _insight(
                "entrance_attraction",
                "warning",
                f"{name}: трафик вырос, входы не изменились",
                (
                    f"Проходящий трафик вырос на {_fmt_pct(traffic_pct)}, а количество входов "
                    f"изменилось на {_fmt_pct(entries_pct)}. Конверсия входа {_fmt_pct(conv_pct)}. "
                    "Это указывает на проблему привлекательности входной зоны, а не на нехватку трафика."
                ),
                {
                    "passersby": {"current": cur["passersby"], "previous": prev["passersby"], "delta_pct": traffic_pct},
                    "entries": {"current": cur["entries"], "previous": prev["entries"], "delta_pct": entries_pct},
                    "entry_conversion": {"current": cur["entry_conversion"], "previous": prev["entry_conversion"]},
                },
                _confidence(days, traffic_pct),
                date_from,
                date_to,
            )
        )

    if conv_pct is not None and conv_pct <= -10:
        out.append(
            _insight(
                "entry_conversion_drop",
                "critical",
                f"{name}: конверсия входа упала на {abs(conv_pct):.1f}%",
                (
                    f"Доля проходящих, которые заходят внутрь, снизилась с {prev['entry_conversion'] * 100:.1f}% "
                    f"до {cur['entry_conversion'] * 100:.1f}%. Проверьте видимость вывески, состояние входной "
                    "группы и наличие препятствий (строительные работы, лотки, парковка)."
                ),
                {
                    "entry_conversion": {"current": cur["entry_conversion"], "previous": prev["entry_conversion"]},
                    "passersby": {"current": cur["passersby"], "previous": prev["passersby"]},
                },
                _confidence(days, conv_pct),
                date_from,
                date_to,
            )
        )

    purchase_pct = d["purchase_conversion"]["pct"]
    if purchase_pct is not None and purchase_pct <= -8:
        out.append(
            _insight(
                "purchase_conversion_drop",
                "warning",
                f"{name}: меньше посетителей доходят до покупки",
                (
                    f"Конверсия посещения в чек снизилась на {abs(purchase_pct):.1f}% "
                    f"({prev['purchase_conversion'] * 100:.1f}% → {cur['purchase_conversion'] * 100:.1f}%). "
                    "Причина внутри точки: очередь, наличие товара, работа персонала или ассортимент."
                ),
                {
                    "purchase_conversion": {"current": cur["purchase_conversion"], "previous": prev["purchase_conversion"]},
                    "entries": {"current": cur["entries"], "previous": prev["entries"]},
                    "receipts": {"current": cur["receipts"], "previous": prev["receipts"]},
                },
                _confidence(days, purchase_pct),
                date_from,
                date_to,
            )
        )

    avg_pct = d["avg_check"]["pct"]
    if avg_pct is not None and avg_pct <= -7:
        out.append(
            _insight(
                "avg_check_drop",
                "warning",
                f"{name}: средний чек снизился на {abs(avg_pct):.1f}%",
                (
                    f"Средний чек {cur['avg_check']:.0f} ₽ против {prev['avg_check']:.0f} ₽ в предыдущем периоде. "
                    "Проверьте состав корзины, допродажи и изменение цен."
                ),
                {
                    "avg_check": {"current": cur["avg_check"], "previous": prev["avg_check"], "delta_pct": avg_pct},
                    "revenue": {"current": cur["revenue"], "previous": prev["revenue"]},
                },
                _confidence(days, avg_pct),
                date_from,
                date_to,
            )
        )

    revenue_pct = d["revenue"]["pct"]
    if revenue_pct is not None and revenue_pct <= -8 and traffic_pct is not None and abs(traffic_pct) < 5:
        out.append(
            _insight(
                "revenue_drop_stable_traffic",
                "critical",
                f"{name}: выручка упала при стабильном трафике",
                (
                    f"Выручка снизилась на {abs(revenue_pct):.1f}%, трафик изменился на {_fmt_pct(traffic_pct)}. "
                    "Проблема не в потоке людей, а в конверсии или чеке внутри точки."
                ),
                {
                    "revenue": {"current": cur["revenue"], "previous": prev["revenue"], "delta_pct": revenue_pct},
                    "passersby": {"current": cur["passersby"], "previous": prev["passersby"]},
                },
                _confidence(days, revenue_pct),
                date_from,
                date_to,
            )
        )

    if cur["attention_rate"] and cur["attention_rate"] < 0.15 and cur["passersby"] > 500:
        out.append(
            _insight(
                "low_attention",
                "warning",
                f"{name}: на вывеску обращают внимание {cur['attention_rate'] * 100:.1f}% проходящих",
                (
                    "Доля людей, которые остановили взгляд или замедлились у витрины, ниже 15%. "
                    "Это косвенный признак слабой заметности оформления."
                ),
                {
                    "attention_rate": cur["attention_rate"],
                    "looked": cur["looked"],
                    "passersby": cur["passersby"],
                },
                0.55,
                date_from,
                date_to,
                ["Показатель внимания приближённый: направление головы и остановки, а не факт прочтения вывески."],
            )
        )

    if revenue_pct is not None and revenue_pct >= 10 and (conv_pct or 0) >= 0:
        out.append(
            _insight(
                "positive_growth",
                "positive",
                f"{name}: рост выручки {_fmt_pct(revenue_pct)}",
                (
                    f"Выручка выросла на {_fmt_pct(revenue_pct)} при конверсии входа {_fmt_pct(conv_pct)}. "
                    "Изменение стоит зафиксировать и проверить, воспроизводится ли оно на других точках."
                ),
                {
                    "revenue": {"current": cur["revenue"], "previous": prev["revenue"]},
                    "entry_conversion": {"current": cur["entry_conversion"], "previous": prev["entry_conversion"]},
                },
                _confidence(days, revenue_pct),
                date_from,
                date_to,
            )
        )

    for anomaly in analytics.anomalies(db, org_id, [location_id]):
        metric_name = "выручка" if anomaly["metric"] == "revenue" else "входы"
        out.append(
            _insight(
                "anomaly",
                "warning" if anomaly["direction"] == "down" else "info",
                f"{name}: аномалия по показателю «{metric_name}»",
                (
                    f"Значение {anomaly['value']} отличается от среднего {anomaly['mean']} "
                    f"на {anomaly['z_score']} стандартных отклонения. Это статистическое отклонение, "
                    "а не доказанная причина."
                ),
                anomaly,
                0.6,
                date.today() - timedelta(days=1),
                date.today(),
            )
        )

    if not out:
        out.append(
            _insight(
                "stable",
                "info",
                f"{name}: значимых отклонений не найдено",
                (
                    f"За период {date_from.isoformat()} — {date_to.isoformat()} показатели точки "
                    "находятся в пределах обычных колебаний."
                ),
                {"current": cur, "previous": prev},
                0.7,
                date_from,
                date_to,
            )
        )

    # Локальная ЦА: пик входов вне описанных окон аудитории
    if audience["segments"]:
        profile = analytics.hourly_profile(db, org_id, [location_id], date_to - timedelta(days=13), date_to)
        peak = max(profile, key=lambda row: row["entries"]) if profile else None
        if peak and peak["entries"] > 0:
            windows = []
            for segment in audience["segments"]:
                start = _minutes(segment["time_from"])
                end = _minutes(segment["time_to"])
                if start is not None and end is not None:
                    windows.append((start, end, segment))
            peak_minutes = peak["hour"] * 60
            covered = any(start <= peak_minutes < end for start, end, _ in windows)
            if windows and not covered:
                out.append(
                    _insight(
                        "audience_peak_mismatch",
                        "warning",
                        f"{name}: пик входов вне описанных окон ЦА",
                        (
                            f"Пик входов приходится на {peak['hour']:02d}:00, но ни один описанный сегмент "
                            "локальной аудитории не покрывает это время. Стоит проверить, кто на самом деле "
                            "проходит мимо в этот час, и обновить профиль ЦА точки."
                        ),
                        {
                            "peak_hour": peak["hour"],
                            "peak_entries": peak["entries"],
                            "audience_windows": [
                                {"segment": s["segment"], "from": s["time_from"], "to": s["time_to"]}
                                for s in audience["segments"]
                            ],
                            "location_context": audience,
                        },
                        0.55,
                        date_to - timedelta(days=13),
                        date_to,
                        ["Профиль ЦА описан вручную и может быть неполным."],
                    )
                )

    for item in out:
        item["evidence"].setdefault("location_context", audience)
    return out


def analyze_network(db: Session, org_id: int, location_ids: list[int], days: int = 28) -> list[dict]:
    """Сравнение точек сети: кто тянет вниз, кто показывает лучший результат."""
    today = date.today()
    date_to = today - timedelta(days=1)
    date_from = date_to - timedelta(days=days - 1)
    ranking = analytics.location_ranking(db, org_id, location_ids, date_from, date_to)
    if len(ranking) < 2:
        return []
    out: list[dict] = []
    best, worst = ranking[0], ranking[-1]
    avg_rev = sum(r["revenue"] for r in ranking) / len(ranking)
    out.append(
        _insight(
            "network_spread",
            "info",
            "Разброс выручки между точками сети",
            (
                f"Лучшая точка — {best['name']} ({_n(best['revenue'])} ₽), худшая — {worst['name']} "
                f"({_n(worst['revenue'])} ₽). Средняя выручка по сети {_n(avg_rev)} ₽. "
                f"Разрыв между крайними точками {((best['revenue'] / worst['revenue'] - 1) * 100 if worst['revenue'] else 0):.0f}%."
            ),
            {"ranking": ranking[:5] + ranking[-3:], "average_revenue": round(avg_rev, 2)},
            0.75,
            date_from,
            date_to,
        )
    )
    low_conv = [r for r in ranking if r["entry_conversion"] and r["entry_conversion"] < 0.06]
    if low_conv:
        out.append(
            _insight(
                "network_low_conversion",
                "warning",
                "Точки с низкой конверсией входа",
                (
                    "Конверсия входа ниже 6% у точек: "
                    + ", ".join(f"{r['name']} ({r['entry_conversion'] * 100:.1f}%)" for r in low_conv)
                    + ". Это кандидаты на проверку вывески и входной группы."
                ),
                {"locations": [{"id": r["location_id"], "name": r["name"], "entry_conversion": r["entry_conversion"]} for r in low_conv]},
                0.7,
                date_from,
                date_to,
            )
        )
    return out


RECOMMENDATION_MAP = {
    "entrance_attraction": {
        "title": "Проверить заметность вывески и входной группы",
        "actions": [
            "Сфотографировать вход с основного направления движения в разное время суток.",
            "Проверить видимость вывески: перекрытия, конкурирующие вывески, угол обзора.",
            "Проверить освещение входной группы в тёмное время.",
            "Подготовить тест нового оформления на 14 дней и зафиксировать изменение в системе.",
        ],
        "expected_effect": "Рост конверсии входа на 5–15% при сохранении трафика",
        "measurement_plan": "Сравнить трафик, входы и покупки за 14 дней до и после изменения с учётом дня недели и времени суток.",
    },
    "entry_conversion_drop": {
        "title": "Разобрать причины падения конверсии входа",
        "actions": [
            "Проверить, не появились ли препятствия у входа (строительство, лотки, транспорт).",
            "Сверить часы падения конверсии с графиком работы и событиями на улице.",
            "Проверить чистоту и освещение входной группы.",
            "Зафиксировать изменение и запустить замер на 14 дней.",
        ],
        "expected_effect": "Возврат конверсии входа к прежнему уровню",
        "measurement_plan": "Сравнение конверсии входа до/после с поправкой на трафик.",
    },
    "purchase_conversion_drop": {
        "title": "Проверить путь посетителя внутри точки",
        "actions": [
            "Сверить часы низкой конверсии с загрузкой персонала и очередью.",
            "Проверить наличие ключевых позиций ассортимента.",
            "Оценить расположение кассы и зоны ожидания.",
            "Запустить замер на 14 дней после изменений.",
        ],
        "expected_effect": "Рост конверсии посещения в чек на 3–8 п.п.",
        "measurement_plan": "Сравнение конверсии посещение→чек и среднего чека до/после.",
    },
    "avg_check_drop": {
        "title": "Проверить средний чек и допродажи",
        "actions": [
            "Сравнить структуру корзины с предыдущим периодом.",
            "Проверить скрипты допродаж и наличие комбо-предложений.",
            "Проверить, не изменились ли цены и скидки.",
        ],
        "expected_effect": "Возврат среднего чека к прежнему уровню",
        "measurement_plan": "Сравнение среднего чека и состава корзины до/после.",
    },
    "revenue_drop_stable_traffic": {
        "title": "Найти причину падения выручки внутри точки",
        "actions": [
            "Разложить выручку по часам и сравнить с трафиком.",
            "Проверить конверсию посещение→чек по часам.",
            "Проверить работу кассы и интеграции с POS на пропуски чеков.",
        ],
        "expected_effect": "Восстановление выручки без роста трафика",
        "measurement_plan": "Сравнение выручки, чеков и конверсии до/после.",
    },
    "low_attention": {
        "title": "Проверить заметность рекламного оформления",
        "actions": [
            "Проверить ракурс камеры, измеряющей внимание к витрине.",
            "Оценить контраст и читаемость вывески с дистанции.",
            "Протестировать альтернативное оформление 14 дней.",
        ],
        "expected_effect": "Рост доли внимания к витрине",
        "measurement_plan": "Сравнение attention_rate и конверсии входа до/после.",
    },
    "positive_growth": {
        "title": "Закрепить и масштабировать удачное изменение",
        "actions": [
            "Зафиксировать, что именно изменилось в точке за период.",
            "Проверить, воспроизводится ли эффект на похожих точках.",
            "Запустить пилот на 2–3 точках с замером 14 дней.",
        ],
        "expected_effect": "Тиражирование роста на другие точки сети",
        "measurement_plan": "Сравнение точек-пилотов с контрольной группой.",
    },
    "anomaly": {
        "title": "Проверить источник аномалии",
        "actions": [
            "Проверить доступность камер и интеграции с кассой за день аномалии.",
            "Сверить данные с фактическими событиями в точке.",
            "Если аномалия подтверждена — зафиксировать изменение и запустить замер.",
        ],
        "expected_effect": "Отделить технический сбой от реального изменения",
        "measurement_plan": "Повторная проверка показателей за 3–7 дней.",
    },
    "network_spread": {
        "title": "Разобрать разрыв между лучшей и худшей точками",
        "actions": [
            "Сравнить лучшую и худшую точки по трафику, конверсии и чеку.",
            "Проверить, отличается ли оформление входа и ассортимент.",
            "Перенести удачные практики из лучшей точки в худшую.",
        ],
        "expected_effect": "Сокращение разрыва между точками сети",
        "measurement_plan": "Сравнение показателей точек до/после переноса практик.",
    },
    "network_low_conversion": {
        "title": "Проверить точки с низкой конверсией входа",
        "actions": [
            "Собрать фото входа по каждой точке-кандидату.",
            "Сравнить с точками-лидерами по конверсии.",
            "Запустить пилот нового оформления на одной точке.",
        ],
        "expected_effect": "Рост конверсии входа в отстающих точках",
        "measurement_plan": "Сравнение конверсии входа до/после по каждой точке.",
    },
    "stable": {
        "title": "Продолжать наблюдение",
        "actions": ["Оставить точку в мониторинге и проверить через 14 дней."],
        "expected_effect": "Раннее обнаружение изменений",
        "measurement_plan": "Регулярный пересчёт показателей.",
    },
    "audience_peak_mismatch": {
        "title": "Уточнить локальную ЦА и окна активности",
        "actions": [
            "Проверить, кто проходит мимо точки в час пика входов.",
            "Обновить профиль ЦА точки: сегменты, время, мотив.",
            "Подобрать сообщение под фактическую аудиторию этого часа.",
            "Замерить изменение входов и чеков за 14 дней.",
        ],
        "expected_effect": "Рост конверсии входа за счёт попадания в реальную аудиторию",
        "measurement_plan": "Сравнение входов и чеков в часы пика до/после изменения сообщения.",
    },
}


def recommendation_for(insight: dict) -> dict:
    template = RECOMMENDATION_MAP.get(insight["kind"], RECOMMENDATION_MAP["stable"])
    return {
        "title": template["title"],
        "rationale": insight["summary"],
        "actions": template["actions"],
        "expected_effect": template["expected_effect"],
        "measurement_plan": template["measurement_plan"],
    }


def persist(db: Session, org_id: int, location_id: int | None, insights: list[dict]) -> list[AiInsight]:
    saved: list[AiInsight] = []
    for item in insights:
        row = AiInsight(
            organization_id=org_id,
            location_id=location_id,
            kind=item["kind"],
            severity=item["severity"],
            title=item["title"],
            summary=item["summary"],
            evidence=item["evidence"],
            confidence=item["confidence"],
            limitations=item["limitations"],
            period_from=datetime.fromisoformat(item["period_from"]),
            period_to=datetime.fromisoformat(item["period_to"]),
            engine=LLM_PROVIDER,
        )
        db.add(row)
        db.flush()
        rec = recommendation_for(item)
        db.add(
            Recommendation(
                organization_id=org_id,
                location_id=location_id,
                insight_id=row.id,
                title=rec["title"],
                rationale=rec["rationale"],
                actions=rec["actions"],
                expected_effect=rec["expected_effect"],
                measurement_plan=rec["measurement_plan"],
            )
        )
        saved.append(row)
    db.commit()
    return saved


def _llm_rewrite(question: str, facts: dict) -> str | None:
    """Адаптер внешней LLM. Без ключа возвращает None — используется детерминированный ответ."""
    result = llm.complete(f"Вопрос пользователя: {question}", facts)
    return result.text if result else None


def answer_question(db: Session, org_id: int, location_ids: list[int], question: str, location_id: int | None = None) -> dict:
    """Ответ на вопрос по данным компании. Считает факты, затем формулирует вывод."""
    q = question.lower()
    today = date.today()
    date_to = today - timedelta(days=1)
    date_from = date_to - timedelta(days=27)
    scope = [location_id] if location_id else location_ids
    cmp = analytics.compare_periods(db, org_id, scope, date_from, date_to)
    cur, prev, d = cmp["current"], cmp["previous"], cmp["delta"]
    ranking = analytics.location_ranking(db, org_id, location_ids, date_from, date_to)
    facts = {
        "period": cmp["period"],
        "current": cur,
        "previous": prev,
        "delta": d,
        "ranking": ranking[:5],
    }

    if any(word in q for word in ("выручк", "деньг", "продаж", "оборот")):
        answer = (
            f"За период {date_from.isoformat()} — {date_to.isoformat()} выручка составила "
            f"{_n(cur['revenue'])} ₽, это {_fmt_pct(d['revenue']['pct'])} к предыдущему периоду. "
            f"Чеков: {_n(cur['receipts'])}, средний чек {_n(cur['avg_check'])} ₽."
        )
    elif any(word in q for word in ("трафик", "проход", "мимо")):
        answer = (
            f"Проходящий трафик за период — {_n(cur['passersby'])} человек ({_fmt_pct(d['passersby']['pct'])}). "
            f"Из них зашли внутрь {_n(cur['entries'])} ({cur['entry_conversion'] * 100:.1f}% конверсия входа)."
        )
    elif any(word in q for word in ("конверс", "вход", "заход")):
        answer = (
            f"Конверсия входа {cur['entry_conversion'] * 100:.1f}% ({_fmt_pct(d['entry_conversion']['pct'])}), "
            f"конверсия посещения в чек {cur['purchase_conversion'] * 100:.1f}% "
            f"({_fmt_pct(d['purchase_conversion']['pct'])})."
        )
    elif any(word in q for word in ("чек", "корзин")):
        answer = (
            f"Средний чек {_n(cur['avg_check'])} ₽ ({_fmt_pct(d['avg_check']['pct'])}). "
            f"Выручка на посетителя {_n(cur['revenue_per_visitor'])} ₽."
        )
    elif any(word in q for word in ("точк", "лучш", "худш", "сравн", "сеть")):
        if ranking:
            best, worst = ranking[0], ranking[-1]
            answer = (
                f"Лучшая точка — {best['name']} ({_n(best['revenue'])} ₽, конверсия входа "
                f"{best['entry_conversion'] * 100:.1f}%). Худшая — {worst['name']} "
                f"({_n(worst['revenue'])} ₽, конверсия входа {worst['entry_conversion'] * 100:.1f}%)."
            )
        else:
            answer = "Недостаточно данных для сравнения точек."
    elif any(word in q for word in ("что делать", "рекоменд", "улучш", "проблем")):
        insights = analyze_location(db, org_id, location_id, 28) if location_id else analyze_network(db, org_id, location_ids, 28)
        top = insights[0] if insights else None
        if top:
            rec = recommendation_for(top)
            answer = f"{top['title']}. {top['summary']} Рекомендация: {rec['title']}. " + " ".join(rec["actions"][:3])
        else:
            answer = "Значимых проблем не обнаружено."
    else:
        answer = (
            f"За период {date_from.isoformat()} — {date_to.isoformat()}: трафик {_n(cur['passersby'])}, "
            f"входы {_n(cur['entries'])}, чеки {_n(cur['receipts'])}, выручка {_n(cur['revenue'])} ₽, "
            f"средний чек {_n(cur['avg_check'])} ₽. Уточните вопрос: трафик, конверсия, выручка, сравнение точек."
        )

    llm_answer = _llm_rewrite(question, facts)
    return {
        "answer": llm_answer or answer,
        "engine": "llm" if llm_answer else "rules",
        "facts": facts,
        "confidence": 0.8 if llm_answer else 0.75,
        "limitations": LIMITATIONS_BASE,
        "sources": [
            "attention_metrics (видеоаналитика, зона прохода)",
            "visitor_metrics (видеоаналитика, зона входа)",
            "transactions (кассовая система)",
        ],
    }
