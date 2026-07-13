# IoTDB History Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make sensor history use IoTDB as the durable source, with backend time-window aggregation and memory fallback only as an explicit diagnostic fallback.

**Architecture:** Sensor collection queues timestamped records and writes every record to IoTDB instead of overwriting samples. The history API computes aligned range windows, queries IoTDB, aggregates by sensor-specific rules, and returns metadata describing source, window, interval, and point count. The frontend consumes the returned window and keeps existing slow-refresh behavior.

**Tech Stack:** FastAPI, Python 3.10, apache-iotdb 1.3.0, Vue 3, ECharts, Node-based utility tests.

---

### Task 1: Backend History Helpers And Tests

**Files:**
- Create: `dam-ai-service/tests/test_iotdb_history.py`
- Modify: `dam-ai-service/app/services/iotdb_service.py`

- [x] Add tests for preserving `0.0`, integer/string fields, aligned range windows, and bucket aggregation.
- [x] Implement pure helper functions in `iotdb_service.py`: safe field value extraction, range config, aligned window calculation, bucket aggregation.
- [x] Run: `python3 -m unittest discover -s tests -v` from `dam-ai-service`.

### Task 2: Durable Write Queue

**Files:**
- Modify: `dam-ai-service/app/services/sensor_collector.py`
- Modify: `dam-ai-service/app/services/iotdb_service.py`

- [x] Replace `batch_data[device_id].update(data)` with timestamped queued records.
- [x] Add `insert_sensor_records(device_id, records)` with per-record fallback to existing SQL insert.
- [x] Track write diagnostics: success count, failure count, last write time, last error.
- [x] Preserve the existing latest-data and short in-memory history behavior.

### Task 3: History API Metadata

**Files:**
- Modify: `dam-ai-service/app/api/sensor.py`

- [x] Call the new IoTDB aggregated query with `device_name`, `device_id`, and `range`.
- [x] Return `source`, `window`, `sample_interval`, `point_count`, `raw_point_count`, and fallback count.
- [x] Only use memory fallback when IoTDB returns no points or errors for the requested window; mark the source accordingly.

### Task 4: Frontend Consumption

**Files:**
- Modify: `dam-frontend/src/utils/sensorHistory.js`
- Modify: four `dam-frontend/src/views/Monitor/Sensor*.vue` pages
- Modify: `dam-frontend/src/utils/sensorHistory.test.mjs`

- [x] Accept backend-returned `window` and `sample_interval` when present.
- [x] Keep frontend normalization only as compatibility for old responses.
- [x] Keep default y-axis ranges and slow refresh.

### Task 5: Verification

- [x] Run backend unittest.
- [ ] Run frontend utility test. Blocked locally: `node` is not installed.
- [x] Run `git diff --check`.
- [ ] Run frontend Vite build. Blocked locally: `node/npm` are not installed and Docker access was rejected by policy/usage limits.
- [ ] Restart `dam-server-python` and `dam-frontend`. Blocked locally: Docker socket access requires escalation and escalation was rejected.
- [ ] Verify `1h/6h/1d/7d` history endpoints include metadata and recent IoTDB points after restart. Blocked by the same Docker/runtime access limitation.
