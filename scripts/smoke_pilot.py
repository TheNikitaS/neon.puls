"""Проверка новых блоков: пилот, ЦА, оценка, гипотезы, тесты, тренды, фото, AI."""

from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8010"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def call(method: str, path: str, body=None, token=None, org=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    if org:
        req.add_header("X-Organization-Id", str(org))
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    login = call("POST", "/api/auth/login", {"email": "demo@neonpulse.ru", "password": "Demo2026!"})
    token, org = login["token"], login["active_org_id"]
    locs = call("GET", "/api/locations", token=token, org=org)
    target = next((l for l in locs if "Невский" in l["name"]), locs[0])
    lid = target["id"]
    print("location:", target["name"], lid)

    pilot = call("GET", f"/api/locations/{lid}/pilot", token=token, org=org)
    print("pilot:", pilot["point_name"], pilot["compare_days"])
    call(
        "PUT",
        f"/api/locations/{lid}/pilot",
        {
            "signage_date": "2026-10-20T00:00:00",
            "camera_date": "2026-10-20T00:00:00",
            "compare_days": 60,
            "avg_check": 520,
            "target_growth": 0.3,
            "min_days_before": 14,
            "min_days_after": 14,
            "point_name": target["name"],
            "address": target["address"],
            "comment": "Пилот вывески",
        },
        token=token,
        org=org,
    )
    print("pilot saved")

    seg = call(
        "POST",
        f"/api/locations/{lid}/audience",
        {
            "weekday": "Будни",
            "time_from": "12:00",
            "time_to": "15:00",
            "segment": "Офисные сотрудники",
            "age": "25–45",
            "composition": "1–2 человека",
            "behavior": "Идут быстро, смотрят 1–2 секунды",
            "motive": "Быстро перекусить",
            "what_works": "Короткая заметная фраза",
        },
        token=token,
        org=org,
    )
    print("audience added:", seg["id"])
    audience = call("GET", f"/api/locations/{lid}/audience", token=token, org=org)
    print("audience rows:", len(audience))

    score = call(
        "PUT",
        f"/api/locations/{lid}/score",
        {"scores": {"visibility": 3, "readability": 5, "contrast": 5, "light": 5, "entrance": 5, "impulse": 5, "photo": 5, "audience": 5, "season": 5, "scale": 5}},
        token=token,
        org=org,
    )
    print("score:", score)

    hyp = call(
        "POST",
        f"/api/locations/{lid}/hypotheses",
        {"hypothesis": "Неоновый контур окон увеличит взгляды", "metric": "Взгляды", "growth": "10–15%", "test_days": "14–30 дней"},
        token=token,
        org=org,
    )
    print("hypothesis:", hyp["id"])
    test = call(
        "POST",
        f"/api/locations/{lid}/tests",
        {"name": "Динамика вывески", "what": "Мягкое мерцание вечером", "metric": "Взгляды", "goal": "+10%"},
        token=token,
        org=org,
    )
    print("test:", test["id"])
    trend = call(
        "POST",
        f"/api/locations/{lid}/trends",
        {"kind": "Погода", "title": "Холодная неделя", "why": "В холод быстрее решают зайти", "idea": "«Согрейся внутри»", "urgency": "Средняя"},
        token=token,
        org=org,
    )
    print("trend:", trend["id"])
    photo = call(
        "POST",
        f"/api/locations/{lid}/photos",
        {"angle": "20–30 метров прямо", "problem": "Проверить дальнюю заметность", "recommendation": "Усилить контур", "priority": "Высокий"},
        token=token,
        org=org,
    )
    print("photo:", photo["id"])

    ai = call("POST", f"/api/ai/analyze/{lid}", token=token, org=org)
    print("insights:", len(ai["insights"]))
    for item in ai["insights"]:
        ctx = item["evidence"].get("location_context", {})
        print("  -", item["kind"], "|", item["title"][:80], "| адрес:", ctx.get("address", "—"))

    ov = call("GET", "/api/analytics/overview", token=token, org=org)
    print("attention_available:", ov["attention_available"], "| looked:", ov["current"]["looked"])

    print("PILOT SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
