"""Модель данных НЕОН.ПУЛЬС (раздел 12 ТЗ)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(24), default=lambda: "org_" + _uid(), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    industry: Mapped[str] = mapped_column(String(80), default="retail")
    plan: Mapped[str] = mapped_column(String(40), default="trial")
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    locations = relationship("Location", back_populates="organization", cascade="all, delete-orphan")
    memberships = relationship("Membership", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    position: Mapped[str] = mapped_column(String(120), default="")
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")


class Membership(Base):
    """Права пользователя внутри организации. scope — список id точек/регионов."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_membership"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(40), default="ANALYST")
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(40), default="")

    locations = relationship("Location", back_populates="region")


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(24), default=lambda: "loc_" + _uid(), unique=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(String(300), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    district: Mapped[str] = mapped_column(String(160), default="")
    attention_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    audience_note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="active")
    timezone: Mapped[str] = mapped_column(String(60), default="Europe/Moscow")
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    organization = relationship("Organization", back_populates="locations")
    region = relationship("Region", back_populates="locations")
    cameras = relationship("Camera", back_populates="location", cascade="all, delete-orphan")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    external_id: Mapped[str] = mapped_column(String(120), default="")
    provider: Mapped[str] = mapped_column(String(40), default="ivideon")
    purpose: Mapped[str] = mapped_column(String(40), default="entrance")  # traffic|entrance|inside|showcase
    status: Mapped[str] = mapped_column(String(24), default="online")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    location = relationship("Location", back_populates="cameras")
    zones = relationship("CameraZone", back_populates="camera", cascade="all, delete-orphan")


class CameraZone(Base):
    __tablename__ = "camera_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(40), default="entry")
    polygon: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    camera = relationship("Camera", back_populates="zones")


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # video | pos | crm | erp | custom
    provider: Mapped[str] = mapped_column(String(60))  # ivideon | generic_pos | custom_rest
    name: Mapped[str] = mapped_column(String(160))
    base_url: Mapped[str] = mapped_column(String(400), default="")
    auth_type: Mapped[str] = mapped_column(String(30), default="api_key")  # api_key|bearer|oauth2|none
    credentials_enc: Mapped[str] = mapped_column(Text, default="")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="draft")  # draft|connected|error|disabled
    sync_interval_min: Mapped[int] = mapped_column(Integer, default=60)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    logs = relationship("IntegrationLog", back_populates="integration", cascade="all, delete-orphan")


class IntegrationLog(Base):
    __tablename__ = "integration_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_id: Mapped[int] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    integration = relationship("Integration", back_populates="logs")


class TrafficEvent(Base):
    """Сырые события трафика (агрегированные по часам) от видеоаналитики."""

    __tablename__ = "traffic_events"
    __table_args__ = (Index("ix_traffic_org_loc_ts", "organization_id", "location_id", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    direction: Mapped[str] = mapped_column(String(20), default="pass")
    count: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.9)
    source: Mapped[str] = mapped_column(String(40), default="ivideon")


class VisitorMetric(Base):
    __tablename__ = "visitor_metrics"
    __table_args__ = (
        Index("ix_visitor_org_loc_ts", "organization_id", "location_id", "ts"),
        UniqueConstraint("location_id", "ts", name="uq_visitor_loc_ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    entries: Mapped[int] = mapped_column(Integer, default=0)
    unique_visitors: Mapped[int] = mapped_column(Integer, default=0)
    dwell_avg_sec: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(40), default="ivideon")


class AttentionMetric(Base):
    __tablename__ = "attention_metrics"
    __table_args__ = (
        Index("ix_attention_org_loc_ts", "organization_id", "location_id", "ts"),
        UniqueConstraint("location_id", "ts", name="uq_attention_loc_ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    passersby: Mapped[int] = mapped_column(Integer, default=0)
    looked: Mapped[int] = mapped_column(Integer, default=0)
    approached: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(40), default="ivideon")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_tx_org_loc_ts", "organization_id", "location_id", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    receipt_no: Mapped[str] = mapped_column(String(60), default="")
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    items_count: Mapped[int] = mapped_column(Integer, default=0)
    discount: Mapped[float] = mapped_column(Float, default=0.0)
    is_return: Mapped[bool] = mapped_column(Boolean, default=False)
    categories: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(40), default="pos")


class RevenueMetric(Base):
    """Дневной срез выручки (материализуется аналитическим ядром)."""

    __tablename__ = "revenue_metrics"
    __table_args__ = (UniqueConstraint("location_id", "day", name="uq_revenue_loc_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))
    day: Mapped[datetime] = mapped_column(DateTime, index=True)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    receipts: Mapped[int] = mapped_column(Integer, default=0)
    avg_check: Mapped[float] = mapped_column(Float, default=0.0)
    returns_amount: Mapped[float] = mapped_column(Float, default=0.0)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(40), default="marketing")
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    budget: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str] = mapped_column(Text, default="")


class Change(Base):
    """Зафиксированное изменение в точке: новая вывеска, витрина, акция, режим работы."""

    __tablename__ = "changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), default="signage")
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    applied_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AiInsight(Base):
    __tablename__ = "ai_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20), default="info")  # info|warning|critical|positive
    title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.6)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    period_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    engine: Mapped[str] = mapped_column(String(40), default="rules")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), nullable=True)
    insight_id: Mapped[int | None] = mapped_column(ForeignKey("ai_insights.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(240))
    rationale: Mapped[str] = mapped_column(Text)
    actions: Mapped[list] = mapped_column(JSON, default=list)
    expected_effect: Mapped[str] = mapped_column(String(300), default="")
    measurement_plan: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="new")  # new|accepted|in_progress|done|rejected
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    effectiveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))
    recommendation_id: Mapped[int | None] = mapped_column(ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True)
    change_id: Mapped[int | None] = mapped_column(ForeignKey("changes.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(240))
    baseline_from: Mapped[datetime] = mapped_column(DateTime)
    baseline_to: Mapped[datetime] = mapped_column(DateTime)
    result_from: Mapped[datetime] = mapped_column(DateTime)
    result_to: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(24), default="running")  # running|finished
    verdict: Mapped[str] = mapped_column(String(24), default="")  # improved|worse|no_change|inconclusive
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    plan: Mapped[str] = mapped_column(String(40), default="trial")
    status: Mapped[str] = mapped_column(String(24), default="active")
    seats: Mapped[int] = mapped_column(Integer, default=5)
    locations_limit: Mapped[int] = mapped_column(Integer, default=10)
    price_month: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="RUB")
    period_start: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), default="anomaly")
    severity: Mapped[str] = mapped_column(String(20), default="warning")
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(60), default="")
    entity_id: Mapped[str] = mapped_column(String(60), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class PilotSettings(Base):
    """Настройки пилота точки: дата установки вывески, период сравнения, экономика."""

    __tablename__ = "pilot_settings"
    __table_args__ = (UniqueConstraint("location_id", name="uq_pilot_location"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    signage_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    camera_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    compare_days: Mapped[int] = mapped_column(Integer, default=60)
    avg_check: Mapped[float] = mapped_column(Float, default=0.0)
    target_growth: Mapped[float] = mapped_column(Float, default=0.3)
    min_days_before: Mapped[int] = mapped_column(Integer, default=30)
    min_days_after: Mapped[int] = mapped_column(Integer, default=30)
    point_name: Mapped[str] = mapped_column(String(160), default="")
    address: Mapped[str] = mapped_column(String(300), default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AudienceSegment(Base):
    """Локальная ЦА точки: кто проходит, когда и что может сработать."""

    __tablename__ = "audience_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[str] = mapped_column(String(40), default="Ежедневно")
    time_from: Mapped[str] = mapped_column(String(8), default="")
    time_to: Mapped[str] = mapped_column(String(8), default="")
    segment: Mapped[str] = mapped_column(String(160))
    age: Mapped[str] = mapped_column(String(40), default="")
    composition: Mapped[str] = mapped_column(String(80), default="")
    behavior: Mapped[str] = mapped_column(Text, default="")
    motive: Mapped[str] = mapped_column(Text, default="")
    what_works: Mapped[str] = mapped_column(Text, default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PointScore(Base):
    """Оценка визуальной эффективности точки (1–5 по параметрам с весами)."""

    __tablename__ = "point_scores"
    __table_args__ = (UniqueConstraint("location_id", name="uq_score_location"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    index_value: Mapped[float] = mapped_column(Float, default=0.0)
    interpretation: Mapped[str] = mapped_column(String(200), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    hypothesis: Mapped[str] = mapped_column(String(300))
    change: Mapped[str] = mapped_column(Text, default="")
    metric: Mapped[str] = mapped_column(String(120), default="")
    current_value: Mapped[str] = mapped_column(String(80), default="")
    expected_value: Mapped[str] = mapped_column(String(80), default="")
    growth: Mapped[str] = mapped_column(String(40), default="")
    test_days: Mapped[str] = mapped_column(String(40), default="")
    result: Mapped[str] = mapped_column(String(40), default="Не начато")
    conclusion: Mapped[str] = mapped_column(Text, default="")
    next_action: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TestPlan(Base):
    __tablename__ = "test_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    what: Mapped[str] = mapped_column(Text, default="")
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metric: Mapped[str] = mapped_column(String(120), default="")
    goal: Mapped[str] = mapped_column(String(80), default="")
    fact: Mapped[str] = mapped_column(String(80), default="")
    result: Mapped[str] = mapped_column(String(40), default="Не начато")
    decision: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Trend(Base):
    __tablename__ = "trends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(60), default="")
    title: Mapped[str] = mapped_column(String(200))
    why: Mapped[str] = mapped_column(Text, default="")
    idea: Mapped[str] = mapped_column(Text, default="")
    urgency: Mapped[str] = mapped_column(String(40), default="")
    effect: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(40), default="Идея")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PhotoAudit(Base):
    __tablename__ = "photo_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500), default="")
    angle: Mapped[str] = mapped_column(String(120), default="")
    good: Mapped[str] = mapped_column(Text, default="")
    bad: Mapped[str] = mapped_column(Text, default="")
    problem: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(40), default="Средний")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ManualDailyMetric(Base):
    """Ручной ввод дневных показателей: для точек без API и кассовых интеграций."""

    __tablename__ = "manual_daily_metrics"
    __table_args__ = (UniqueConstraint("location_id", "day", name="uq_manual_loc_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    day: Mapped[datetime] = mapped_column(DateTime, index=True)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    receipts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entries: Mapped[int | None] = mapped_column(Integer, nullable=True)
    looked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passersby: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
