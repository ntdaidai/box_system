# Sensor History Rollup Design

## Goal

Build a durable sensor history module that separates raw telemetry, archived raw data, and precomputed rollup data so monitor pages can query long ranges without ad hoc aggregation in the frontend.

## Data Layers

- Raw telemetry is first committed to a local SQLite WAL queue and is removed only after IoTDB acknowledges the original timestamped write.
- Raw online data remains in IoTDB under `root.dam.sensor.{device_id}`.
- Raw archive data is exported as daily CSV files under `/home/jetson/data/archive/sensors/YYYY-MM-DD/{device_id}.csv`.
- Rollup data is stored in IoTDB under `root.dam.rollup_{level}.{device_id}`.

## Query Ranges

| UI range | Window | Rollup level | Bucket size |
| --- | ---: | --- | ---: |
| `1h` | last 1 hour | `1m` | 1 minute |
| `6h` | last 6 hours | `10m` | 10 minutes |
| `1d` | last 24 hours | `30m` | 30 minutes |
| `7d` | last 7 days | `1h` | 1 hour |
| `6mo` | last 180 days | `1d` | 1 day |

## Retention

- Raw online IoTDB data: 14 days.
- Raw CSV archive: long-term retention outside IoTDB.
- `rollup_1m`: 14 days.
- `rollup_10m`: 30 days.
- `rollup_30m`: 90 days.
- `rollup_1h`: 1 year.
- `rollup_1d`: at least 5 years.

## Aggregation Standards

- Temperature and humidity use arithmetic average for the selected bucket.
- Wind speed and wind level use arithmetic average for the selected bucket.
- Wind direction angle uses circular mean. Wind direction text/code use the nearest canonical direction from the circular mean.
- Rain fields continue to use arithmetic average for the selected bucket.
- Vibration fields are passed through using the current average strategy for now, while preserving the same history response template.

## API Contract

The existing endpoint stays stable:

`GET /v1/sensor/history/{device_name}?range=1h|6h|1d|7d|6mo`

The response returns normalized chart-ready points:

```json
{
  "device_name": "wind",
  "source": "rollup",
  "rollup_level": "10m",
  "window": { "start": 1782934200, "end": 1782955800 },
  "sample_interval": 600,
  "history": [
    { "timestamp": 1782934800, "data": { "wind_speed_ms": 3.2, "wind_angle": 135.0 } }
  ]
}
```

Frontend history utilities should only fill missing buckets and format axes. They must not re-aggregate returned values.

The history response itself is not cached in Redis. Rollup queries are the backend acceleration layer; this prevents repaired data from remaining hidden behind a stale server-side response cache.

## Background Processing

The backend owns a rollup service that can:

- Build closed buckets for all rollup levels.
- Read raw or lower-level rollup source data.
- Apply the per-sensor aggregation strategy.
- Upsert rollup points into IoTDB.
- Export raw data to daily CSV archive files.

For implementation, the service should expose synchronous methods that are easy to unit test. Scheduling can run in a lightweight background thread from application startup.

Rollup checkpoints and archive completion manifests are durable. A restart resumes missing buckets and archive days instead of treating in-memory scheduler state as completion. Raw retention is paused while any archive day is incomplete.

## Operations

`GET /v1/sensor/history/status` reports raw-device freshness, durable queue age, rollup lag, and archive backlog. Docker runs `scripts/check_history_health.py` every 30 seconds and marks the backend unhealthy when freshness, queue age, storage access, or rollup lag crosses its threshold.

## Migration

The initial implementation should support rebuilding rollups from existing raw IoTDB data. The history API should fall back to raw aggregation only when rollup data is missing, and should report that fallback through the `source` field.
