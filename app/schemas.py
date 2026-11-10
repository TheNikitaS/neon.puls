"""Pydantic-схемы запросов и ответов."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=200)
    company_name: str = Field(min_length=2, max_length=200)
    industry: str = "retail"


class LoginIn(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=200)
    password: str


class TokenOut(BaseModel):
    token: str
    user: dict
    organizations: list[dict]
    active_org_id: int | None


class LocationIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    city: str = ""
    address: str = ""
    region_id: int | None = None
    status: str = "active"
    area_m2: float | None = None


class LocationPatch(BaseModel):
    name: str | None = None
    city: str | None = None
    address: str | None = None
    region_id: int | None = None
    status: str | None = None
    area_m2: float | None = None


class CameraIn(BaseModel):
    name: str
    external_id: str = ""
    provider: str = "ivideon"
    purpose: Literal["traffic", "entrance", "inside", "showcase"] = "entrance"
    status: str = "online"


class IntegrationIn(BaseModel):
    kind: Literal["video", "pos", "crm", "erp", "custom"]
    provider: str
    name: str
    base_url: str = ""
    auth_type: Literal["api_key", "bearer", "oauth2", "none"] = "api_key"
    credentials: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    sync_interval_min: int = 60


class IntegrationPatch(BaseModel):
    name: str | None = None
    base_url: str | None = None
    auth_type: str | None = None
    credentials: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    sync_interval_min: int | None = None
    status: str | None = None


class ChangeIn(BaseModel):
    location_id: int
    kind: str = "signage"
    title: str
    description: str = ""
    applied_at: datetime


class RecommendationPatch(BaseModel):
    status: Literal["new", "accepted", "in_progress", "done", "rejected"]


class ExperimentIn(BaseModel):
    location_id: int
    change_id: int | None = None
    recommendation_id: int | None = None
    title: str
    baseline_days: int = 14
    result_days: int = 14


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    location_id: int | None = None


class MemberIn(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=200)
    full_name: str
    role: Literal["ORG_ADMIN", "NETWORK_MANAGER", "REGIONAL_MANAGER", "LOCATION_MANAGER", "ANALYST"] = "ANALYST"
    password: str | None = None
    scope: dict[str, Any] = Field(default_factory=dict)


class MemberPatch(BaseModel):
    role: str | None = None
    scope: dict[str, Any] | None = None
    is_active: bool | None = None


class PilotIn(BaseModel):
    signage_date: datetime | None = None
    camera_date: datetime | None = None
    compare_days: int = 60
    avg_check: float = 0.0
    target_growth: float = 0.3
    min_days_before: int = 30
    min_days_after: int = 30
    point_name: str = ""
    address: str = ""
    comment: str = ""


class AudienceIn(BaseModel):
    weekday: str = "Ежедневно"
    time_from: str = ""
    time_to: str = ""
    segment: str = Field(min_length=1, max_length=160)
    age: str = ""
    composition: str = ""
    behavior: str = ""
    motive: str = ""
    what_works: str = ""
    comment: str = ""


class ScoreIn(BaseModel):
    scores: dict[str, int] = Field(default_factory=dict)


class HypothesisIn(BaseModel):
    hypothesis: str = Field(min_length=3, max_length=300)
    change: str = ""
    metric: str = ""
    current_value: str = ""
    expected_value: str = ""
    growth: str = ""
    test_days: str = ""
    result: str = "Не начато"
    conclusion: str = ""
    next_action: str = ""


class TestPlanIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    what: str = ""
    start_date: datetime | None = None
    end_date: datetime | None = None
    metric: str = ""
    goal: str = ""
    fact: str = ""
    result: str = "Не начато"
    decision: str = ""


class TrendIn(BaseModel):
    kind: str = ""
    title: str = Field(min_length=2, max_length=200)
    why: str = ""
    idea: str = ""
    urgency: str = ""
    effect: str = ""
    status: str = "Идея"


class PhotoAuditIn(BaseModel):
    url: str = ""
    angle: str = ""
    good: str = ""
    bad: str = ""
    problem: str = ""
    recommendation: str = ""
    priority: str = "Средний"


class ManualMetricIn(BaseModel):
    day: date
    revenue: float | None = None
    receipts: int | None = None
    entries: int | None = None
    looked: int | None = None
    passersby: int | None = None
    note: str = ""
