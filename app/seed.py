"""Демонстрационные данные: сеть кофеен, 12 точек, 60 дней метрик и чеков.

Данные синтетические и детерминированные: один и тот же запуск даёт одну и ту же
картину. Это нужно, чтобы демо и проверки были воспроизводимыми.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    AttentionMetric,
    Camera,
    CameraZone,
    Change,
    Integration,
    Location,
    Membership,
    Notification,
    Organization,
    Region,
    Subscription,
    Transaction,
    User,
    VisitorMetric,
)
from .security import encrypt_credentials, hash_password

DAYS = 60

LOCATIONS = [
    # name, city, address, factor (трафик), entry_conv, purchase_conv, avg_check, problem
    ("Невский проспект", "Санкт-Петербург", "Невский пр., 88", 1.55, 0.075, 0.66, 520, "traffic_up_entries_flat"),
    ("Лиговский проспект", "Санкт-Петербург", "Лиговский пр., 55", 1.10, 0.092, 0.70, 480, "improved"),
    ("Петроградская", "Санкт-Петербург", "Каменноостровский пр., 24", 0.95, 0.088, 0.68, 505, None),
    ("Васильевский остров", "Санкт-Петербург", "7-я линия В.О., 34", 0.80, 0.081, 0.64, 470, None),
    ("Московский проспект", "Санкт-Петербург", "Московский пр., 189", 0.90, 0.070, 0.62, 455, "low_conversion"),
    ("Арбат", "Москва", "ул. Арбат, 24", 1.70, 0.068, 0.61, 610, None),
    ("Тверская", "Москва", "ул. Тверская, 12", 1.85, 0.072, 0.63, 640, None),
    ("Хамовники", "Москва", "ул. Льва Толстого, 18", 0.85, 0.095, 0.71, 560, None),
    ("Патриаршие пруды", "Москва", "Малая Бронная, 4", 0.75, 0.101, 0.73, 590, None),
    ("Сокол", "Москва", "Ленинградский пр., 74", 0.70, 0.083, 0.66, 500, None),
    ("Кутузовский", "Москва", "Кутузовский пр., 30", 0.88, 0.078, 0.65, 530, None),
    ("Новая Голландия", "Санкт-Петербург", "наб. Адмиралтейского канала, 2", 0.65, 0.105, 0.72, 545, None),
]


def _hour_weights() -> list[float]:
    weights = []
    for hour in range(24):
        if 8 <= hour <= 10:
            weights.append(1.4)
        elif 11 <= hour <= 15:
            weights.append(1.8)
        elif 16 <= hour <= 19:
            weights.append(1.5)
        elif 20 <= hour <= 21:
            weights.append(0.9)
        else:
            weights.append(0.0)
    return weights


def seed(db: Session) -> bool:
    if db.scalar(select(func.count(Organization.id))):
        return False

    superadmin = User(
        email="admin@neonpulse.ru",
        password_hash=hash_password("NeonPulse2026!"),
        full_name="Администратор платформы",
        position="Суперадминистратор Неон.Пульс",
        is_superadmin=True,
    )
    db.add(superadmin)

    org = Organization(name="Сеть кофеен «Неон»", slug="neon-coffee", industry="coffee", plan="business")
    db.add(org)
    db.flush()

    admin = User(
        email="demo@neonpulse.ru",
        password_hash=hash_password("Demo2026!"),
        full_name="Никита Сухотин",
        position="Руководитель сети",
    )
    db.add(admin)
    db.flush()
    db.add(Membership(user_id=admin.id, organization_id=org.id, role="ORG_ADMIN", scope={}))
    db.add(
        Subscription(
            organization_id=org.id,
            plan="business",
            seats=10,
            locations_limit=25,
            price_month=24900,
            period_end=datetime.utcnow() + timedelta(days=300),
        )
    )

    analyst = User(
        email="analyst@neonpulse.ru",
        password_hash=hash_password("Analyst2026!"),
        full_name="Анна Ким",
        position="Аналитик сети",
    )
    db.add(analyst)
    db.flush()
    db.add(Membership(user_id=analyst.id, organization_id=org.id, role="ANALYST", scope={}))

    spb = Region(organization_id=org.id, name="Санкт-Петербург", code="SPB")
    msk = Region(organization_id=org.id, name="Москва", code="MSK")
    db.add_all([spb, msk])
    db.flush()

    today = date.today()
    start = today - timedelta(days=DAYS)
    weights = _hour_weights()
    weight_sum = sum(weights)

    locations: list[Location] = []
    for idx, (name, city, address, factor, entry_conv, purchase_conv, avg_check, problem) in enumerate(LOCATIONS):
        loc = Location(
            organization_id=org.id,
            region_id=spb.id if city == "Санкт-Петербург" else msk.id,
            name=name,
            city=city,
            address=address,
            status="active",
            area_m2=round(60 + idx * 4.5, 1),
            opened_at=datetime.utcnow() - timedelta(days=400 + idx * 30),
        )
        db.add(loc)
        db.flush()
        locations.append(loc)
        for purpose, label in (("traffic", "Камера трафика"), ("entrance", "Камера входа")):
            cam = Camera(
                location_id=loc.id,
                name=f"{label} · {name}",
                external_id=f"ivideon_{loc.id}_{purpose}",
                provider="ivideon",
                purpose=purpose,
                status="online" if idx != 4 else "offline",
                last_seen_at=datetime.utcnow() - timedelta(minutes=3 if idx != 4 else 240),
            )
            db.add(cam)
            db.flush()
            db.add(
                CameraZone(
                    camera_id=cam.id,
                    name="Зона входа" if purpose == "entrance" else "Зона прохода",
                    kind="entry" if purpose == "entrance" else "passage",
                    polygon=[[0.1, 0.2], [0.9, 0.2], [0.9, 0.9], [0.1, 0.9]],
                )
            )

    db.flush()

    attention_rows: list[dict] = []
    visitor_rows: list[dict] = []
    tx_rows: list[dict] = []

    for idx, loc in enumerate(locations):
        _, _, _, factor, entry_conv, purchase_conv, avg_check, problem = LOCATIONS[idx]
        rnd = random.Random(f"seed:{loc.id}")
        for day_offset in range(DAYS):
            day = start + timedelta(days=day_offset)
            weekday = day.weekday()
            weekend = 1.25 if weekday >= 5 else 1.0
            trend = 1 + day_offset / DAYS * 0.06
            noise = rnd.uniform(0.9, 1.1)
            passersby = int(1400 * factor * weekend * trend * noise)
            looked = int(passersby * rnd.uniform(0.16, 0.28))
            approached = int(looked * rnd.uniform(0.32, 0.48))

            entries = int(passersby * entry_conv * rnd.uniform(0.92, 1.08))
            receipts = int(entries * purchase_conv * rnd.uniform(0.9, 1.1))

            # Сценарий «трафик вырос, входы не изменились» — последние 28 дней
            if problem == "traffic_up_entries_flat" and day_offset >= DAYS - 28:
                passersby = int(passersby * 1.12)
                looked = int(looked * 1.10)
                approached = int(approached * 1.05)
            if problem == "improved" and day_offset >= DAYS - 28:
                entries = int(entries * 1.09)
                receipts = int(receipts * 1.12)
            if problem == "low_conversion":
                entries = int(entries * 0.82)
                receipts = int(receipts * 0.8)

            attention_rows.append(
                {
                    "organization_id": org.id,
                    "location_id": loc.id,
                    "ts": datetime.combine(day, datetime.min.time()),
                    "passersby": passersby,
                    "looked": looked,
                    "approached": approached,
                    "source": "ivideon",
                }
            )

            for hour in range(24):
                if weights[hour] <= 0:
                    continue
                share = weights[hour] / weight_sum
                hour_entries = max(0, int(entries * share * rnd.uniform(0.85, 1.15)))
                if hour_entries == 0:
                    continue
                visitor_rows.append(
                    {
                        "organization_id": org.id,
                        "location_id": loc.id,
                        "ts": datetime.combine(day, datetime.min.time()) + timedelta(hours=hour),
                        "entries": hour_entries,
                        "unique_visitors": int(hour_entries * 0.93),
                        "dwell_avg_sec": round(rnd.uniform(180, 420), 1),
                        "source": "ivideon",
                    }
                )

            for n in range(receipts):
                hour = rnd.choices(range(24), weights=weights, k=1)[0]
                amount = round(max(120.0, rnd.gauss(avg_check, avg_check * 0.35)), 2)
                is_return = rnd.random() < 0.012
                tx_rows.append(
                    {
                        "organization_id": org.id,
                        "location_id": loc.id,
                        "ts": datetime.combine(day, datetime.min.time())
                        + timedelta(hours=hour, minutes=rnd.randint(0, 59)),
                        "receipt_no": f"{loc.id}-{day.strftime('%Y%m%d')}-{n:04d}",
                        "amount": amount,
                        "items_count": rnd.randint(1, 5),
                        "discount": round(amount * rnd.choice([0, 0, 0, 0.05, 0.1]), 2),
                        "is_return": is_return,
                        "categories": rnd.sample(["кофе", "десерт", "завтрак", "напиток", "выпечка"], k=rnd.randint(1, 3)),
                        "source": "pos",
                    }
                )

    db.bulk_insert_mappings(AttentionMetric, attention_rows)
    db.bulk_insert_mappings(VisitorMetric, visitor_rows)
    db.bulk_insert_mappings(Transaction, tx_rows)
    db.flush()

    # Изменения в точках (для сценария «до/после»)
    nevsky = locations[0]
    ligovsky = locations[1]
    db.add_all(
        [
            Change(
                organization_id=org.id,
                location_id=nevsky.id,
                kind="signage",
                title="Замена вывески на светодиодную",
                description="Новая вывеска с внутренней подсветкой, монтаж завершён.",
                applied_at=datetime.combine(today - timedelta(days=21), datetime.min.time()),
                created_by=admin.id,
            ),
            Change(
                organization_id=org.id,
                location_id=ligovsky.id,
                kind="showcase",
                title="Обновление витрины и меню на входе",
                description="Новые постеры, меню на входной группе, подсветка витрины.",
                applied_at=datetime.combine(today - timedelta(days=28), datetime.min.time()),
                created_by=admin.id,
            ),
            Change(
                organization_id=org.id,
                location_id=locations[4].id,
                kind="promo",
                title="Запуск утреннего комбо",
                description="Комбо «кофе + круассан» до 11:00.",
                applied_at=datetime.combine(today - timedelta(days=14), datetime.min.time()),
                created_by=admin.id,
            ),
        ]
    )

    # Интеграции
    ivideon = Integration(
        organization_id=org.id,
        kind="video",
        provider="ivideon",
        name="Ivideon · видеоаналитика",
        base_url="https://api.ivideon.com",
        auth_type="api_key",
        credentials_enc=encrypt_credentials({"api_key": "sandbox-ivideon-key"}),
        config={"location_ids": [loc.id for loc in locations], "zones": ["passage", "entrance", "showcase"]},
        status="connected",
        sync_interval_min=30,
        last_sync_at=datetime.utcnow() - timedelta(minutes=12),
    )
    pos = Integration(
        organization_id=org.id,
        kind="pos",
        provider="generic_pos",
        name="Касса · универсальный коннектор",
        base_url="https://pos.example.com/api",
        auth_type="bearer",
        credentials_enc=encrypt_credentials({"token": "sandbox-pos-token"}),
        config={
            "location_ids": [loc.id for loc in locations],
            "mapping": {
                "path": "/receipts",
                "items_path": "data",
                "amount": "total",
                "ts": "closed_at",
                "receipt_no": "number",
                "items_count": "items_count",
                "discount": "discount",
                "is_return": "is_return",
            },
        },
        status="connected",
        sync_interval_min=15,
        last_sync_at=datetime.utcnow() - timedelta(minutes=6),
    )
    crm = Integration(
        organization_id=org.id,
        kind="crm",
        provider="custom_rest",
        name="CRM клиента",
        base_url="https://crm.example.com/api/v1/metrics",
        auth_type="bearer",
        credentials_enc=encrypt_credentials({"token": "sandbox-crm-token"}),
        config={"location_ids": [loc.id for loc in locations]},
        status="draft",
        sync_interval_min=120,
    )
    db.add_all([ivideon, pos, crm])

    db.add(
        Notification(
            organization_id=org.id,
            location_id=locations[4].id,
            kind="integration",
            severity="critical",
            title="Камера входа не передаёт данные",
            body="Точка «Московский проспект»: камера входа offline более 4 часов. Проверьте питание и сеть.",
        )
    )
    db.add(
        Notification(
            organization_id=org.id,
            location_id=nevsky.id,
            kind="anomaly",
            severity="warning",
            title="Невский проспект: трафик вырос, входы не изменились",
            body="За последние 28 дней проходящий трафик вырос на 12%, количество входов осталось прежним.",
        )
    )

    db.commit()
    return True
