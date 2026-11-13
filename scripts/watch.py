#!/usr/bin/env python3
"""Call a URL a few times a second until stopped, then report how many calls failed.

    python3 scripts/watch.py http://127.0.0.1:8080/api/ready &
    ...deploy something...
    kill -TERM %1        # prints the summary; exits 1 if any call failed

Used in CI to check that users wouldn't notice a bad release being refused and
rolled back. Standard library only.
"""
from __future__ import annotations

import signal
import sys
import time
import urllib.error
import urllib.request

url = sys.argv[1]
calls = 0
failures: list[str] = []


def stop(*_: object) -> None:
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, stop)
started = time.monotonic()
try:
    while True:
        calls += 1
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status != 200:
                    failures.append(f"{time.monotonic() - started:6.1f}s HTTP {response.status}")
        except (urllib.error.URLError, OSError) as error:
            failures.append(f"{time.monotonic() - started:6.1f}s {error}")
        time.sleep(0.2)
except KeyboardInterrupt:
    pass

print(f"{calls} calls to {url} over {time.monotonic() - started:.0f}s, {len(failures)} failed")
for failure in failures[:20]:
    print("  ", failure)
sys.exit(1 if failures else 0)
