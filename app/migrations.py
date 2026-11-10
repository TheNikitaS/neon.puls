"""Лёгкие миграции для SQLite: добавление новых колонок без потери данных."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

LOCATION_COLUMNS = {
    "district": "VARCHAR(160) DEFAULT ''",
    "attention_enabled": "BOOLEAN DEFAULT TRUE",
    "audience_note": "TEXT DEFAULT ''",
}


def ensure_columns(engine: Engine) -> list[str]:
    inspector = inspect(engine)
    if "locations" not in inspector.get_table_names():
        return []
    existing = {column["name"] for column in inspector.get_columns("locations")}
    applied: list[str] = []
    with engine.begin() as conn:
        for name, ddl in LOCATION_COLUMNS.items():
            if name in existing:
                continue
            conn.execute(text(f"ALTER TABLE locations ADD COLUMN {name} {ddl}"))
            applied.append(name)
    return applied
