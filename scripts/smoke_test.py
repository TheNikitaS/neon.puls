"""Сквозная проверка API НЕОН.ПУЛЬС."""

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
    print("login ok, org =", org)

    locs = call("GET", "/api/locations", token=token, org=org)
    print("locations:", len(locs), "|", ", ".join(l["name"] for l in locs[:4]))

    ov = call("GET", "/api/analytics/overview", token=token, org=org)
    print(
        "overview: revenue=%.0f traffic=%d entries=%d receipts=%d conv=%.3f"
        % (
            ov["current"]["revenue"],
            ov["current"]["passersby"],
            ov["current"]["entries"],
            ov["current"]["receipts"],
            ov["current"]["entry_conversion"],
        )
    )
    print("series:", len(ov["series"]), "ranking:", len(ov["ranking"]))

    target = next((l for l in locs if "Невский" in l["name"]), locs[0])
    cmp = call("GET", f"/api/analytics/compare?location_ids={target['id']}", token=token, org=org)
    print("target:", target["name"])
    print("deltas:", {k: cmp["delta"][k]["pct"] for k in ("passersby", "entries", "entry_conversion", "revenue")})

    ai = call("POST", f"/api/ai/analyze/{target['id']}", token=token, org=org)
    for item in ai["insights"]:
        print("  insight:", item["kind"], item["severity"], round(item["confidence"], 2), "|", item["title"][:70])

    net = call("POST", "/api/ai/analyze-network", token=token, org=org)
    print("network insights:", len(net["insights"]))

    ask = call("POST", "/api/ai/ask", {"question": "почему упала выручка"}, token=token, org=org)
    print("ask:", ask["answer"][:140])

    ints = call("GET", "/api/integrations", token=token, org=org)
    print("integrations:", [(i["name"], i["status"]) for i in ints])
    sync = call("POST", f"/api/integrations/{ints[0]['id']}/sync", token=token, org=org)
    print("sync:", sync)
    logs = call("GET", f"/api/integrations/{ints[0]['id']}/logs", token=token, org=org)
    print("logs:", len(logs), "|", logs[0]["message"][:90])

    recs = call("GET", "/api/ai/recommendations", token=token, org=org)
    print("recommendations:", len(recs), "|", recs[0]["title"] if recs else "—")

    notif = call("POST", "/api/notifications/scan", token=token, org=org)
    print("notifications scan:", notif["created"])

    admin = call("POST", "/api/auth/login", {"email": "admin@neonpulse.ru", "password": "NeonPulse2026!"})
    stats = call("GET", "/api/admin/stats", token=admin["token"], org=admin["active_org_id"])
    print("admin stats:", stats)

    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
