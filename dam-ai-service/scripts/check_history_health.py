#!/usr/bin/env python3
"""Exit non-zero when the online sensor-history chain is unhealthy."""

import argparse
import json
import os
import sys
from urllib.request import ProxyHandler, build_opener


def evaluate(payload: dict, max_queue_age: float, max_rollup_lag: int) -> list[str]:
    data = payload.get("data") or {}
    failures = []

    storage = data.get("history_storage") or {}
    if storage.get("status") not in {"healthy", "recovering"}:
        failures.append(f"history_storage={storage.get('status', 'missing')}")
    if storage.get("fresh_device_count") != storage.get("device_count"):
        failures.append(
            f"fresh_devices={storage.get('fresh_device_count')}/{storage.get('device_count')}"
        )

    queue = data.get("pending_queue") or {}
    queue_age = float(queue.get("oldest_age_seconds") or 0)
    if queue_age > max_queue_age:
        failures.append(f"queue_oldest_age={queue_age:.1f}s")

    for level, status in (storage.get("rollup_lag") or {}).items():
        lag = status.get("lag_buckets")
        if lag is not None and int(lag) > max_rollup_lag:
            failures.append(f"rollup_{level}_lag={lag}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        default=f"http://127.0.0.1:{os.getenv('APP_PORT', '8090')}/api/v1/sensor/history/status",
    )
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--max-queue-age", type=float, default=120)
    parser.add_argument("--max-rollup-lag", type=int, default=10)
    args = parser.parse_args()

    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(args.url, timeout=args.timeout) as response:
            payload = json.load(response)
    except Exception as error:
        print(f"history health request failed: {error}", file=sys.stderr)
        return 1

    failures = evaluate(payload, args.max_queue_age, args.max_rollup_lag)
    summary = {
        "healthy": not failures,
        "failures": failures,
        "pending_queue": (payload.get("data") or {}).get("pending_queue"),
        "history_storage": (payload.get("data") or {}).get("history_storage"),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
