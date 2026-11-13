#!/usr/bin/env python3
"""Walk one request through the whole flow against a running copy of the app.

    python3 scripts/smoke.py http://127.0.0.1:3000

Everything goes through the frontend, so one run checks the page, the /api
proxy, the backend and the database together. Standard library only.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000").rstrip("/")


def call(method: str, path: str, person: str | None = None, body: dict | None = None) -> tuple[int, str]:
    request = urllib.request.Request(
        BASE + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json", **({"X-Acting-As": person} if person else {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def expect(what: str, result: tuple[int, str], status: int):
    got, text = result
    if got != status:
        sys.exit(f"FAIL {what}: expected {status}, got {got}: {text[:300]}")
    print(f"ok   {what}")
    return json.loads(text) if text[:1] in "{[" else text


def wait_for_app(seconds: int = 60) -> None:
    # A fresh deployment can take a moment before the first request gets through.
    deadline = time.monotonic() + seconds
    while True:
        try:
            if call("GET", "/api/ready")[0] == 200:
                return
        except OSError:
            pass
        if time.monotonic() > deadline:
            sys.exit(f"FAIL the app at {BASE} wasn't ready within {seconds}s")
        time.sleep(1)


def main() -> None:
    wait_for_app()
    page = expect("home page", call("GET", "/"), 200)
    if "ServiceOps Workbench" not in page:
        sys.exit("FAIL home page: the title isn't on it")

    created = expect(
        "Asha raises a request",
        call("POST", "/api/requests", "asha", {"title": "Smoke test: VPN access", "category": "access"}),
        201,
    )
    path = f"/api/requests/{created['id']}"
    expect("Asha can't approve it herself", call("POST", f"{path}/approve", "asha", {}), 403)
    expect("Ravi triages it", call("POST", f"{path}/triage", "ravi", {"priority": "low"}), 200)
    expect("Meera approves it", call("POST", f"{path}/approve", "meera", {}), 200)
    done = expect("Ravi marks it done", call("POST", f"{path}/complete", "ravi", {"note": "Done by the smoke test"}), 200)
    if done["status"] != "done" or done["decided_by"] != "meera":
        sys.exit(f"FAIL final state: {done}")
    events = expect("its history", call("GET", f"{path}/events"), 200)
    if [e["action"] for e in events] != ["created", "triaged", "approved", "completed"]:
        sys.exit(f"FAIL history: {[e['action'] for e in events]}")
    print(f"PASS request #{created['id']} went from new to done through {BASE}")


if __name__ == "__main__":
    main()
