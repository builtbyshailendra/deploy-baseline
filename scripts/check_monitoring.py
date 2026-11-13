#!/usr/bin/env python3
"""Check the monitoring in the compose stack, after scripts/smoke.py has run once.

    python3 scripts/check_monitoring.py

- Prometheus is scraping the backend, and has seen the smoke test's request done.
- Every query on the dashboard is valid PromQL that Prometheus accepts.
- Grafana is up and has loaded the dashboard.
Standard library only.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROMETHEUS = "http://127.0.0.1:9090"
GRAFANA = "http://127.0.0.1:3001"
DASHBOARD = Path(__file__).resolve().parent.parent / "monitoring/grafana/dashboards/serviceops.json"


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.load(response)


def query(expr: str) -> dict:
    try:
        return get(f"{PROMETHEUS}/api/v1/query?" + urllib.parse.urlencode({"query": expr}))
    except urllib.error.HTTPError as error:
        return json.load(error)  # Prometheus explains a bad query in the body


def eventually(what: str, check, seconds: int = 90) -> None:
    # Prometheus scrapes every 5 seconds and Grafana takes a while to start.
    deadline = time.monotonic() + seconds
    last = "no answer yet"
    while time.monotonic() < deadline:
        try:
            result = check()
            if result is True:
                print(f"ok   {what}")
                return
            last = result
        except OSError as error:
            last = str(error)
        time.sleep(2)
    sys.exit(f"FAIL {what}: {last}")


def backend_is_scraped():
    targets = get(f"{PROMETHEUS}/api/v1/targets")["data"]["activeTargets"]
    health = [t["health"] for t in targets if t["labels"].get("job") == "backend"]
    return health == ["up"] or f"backend target health: {health}"


def smoke_request_counted():
    result = query('max(serviceops_requests{status="done"})')["data"]["result"]
    return (bool(result) and float(result[0]["value"][1]) >= 1) or f"done requests: {result}"


def dashboard_loaded():
    hits = get(f"{GRAFANA}/api/search?" + urllib.parse.urlencode({"query": "ServiceOps"}))
    return any(h.get("uid") == "serviceops" for h in hits) or f"search found: {hits}"


def main() -> None:
    eventually("Prometheus scrapes the backend", backend_is_scraped)
    eventually("Prometheus has the smoke test's request as done", smoke_request_counted)

    panels = json.loads(DASHBOARD.read_text(encoding="utf-8"))["panels"]
    for panel in panels:
        for target in panel["targets"]:
            answer = query(target["expr"])
            if answer.get("status") != "success":
                sys.exit(f"FAIL panel '{panel['title']}': {answer}")
    print(f"ok   all {len(panels)} dashboard queries are valid PromQL")

    eventually("Grafana is up", lambda: get(f"{GRAFANA}/api/health").get("database") == "ok" or "not yet")
    eventually("Grafana has the ServiceOps dashboard", dashboard_loaded)
    print("PASS monitoring")


if __name__ == "__main__":
    main()
