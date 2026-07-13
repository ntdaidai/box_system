# Sensor History Rollup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a unified backend history module with IoTDB rollup layers, raw CSV archiving, fixed aggregation standards, and frontend chart usage that no longer performs business aggregation.

**Architecture:** Add a backend history package for range configuration, aggregation strategies, rollup IO, and archive export. Keep the public sensor history API stable while changing its internals to prefer rollup data. Update frontend history normalization so it fills bucket gaps without averaging already-rolluped values.

**Tech Stack:** Python FastAPI service, Apache IoTDB Python client, CSV archive files, Vue 3 frontend, ECharts.

## Global Constraints

- Preserve existing endpoint path `/v1/sensor/history/{device_name}`.
- Add range `6mo`.
- Store archives under `/home/jetson/data/archive/sensors/YYYY-MM-DD/{device_id}.csv`.
- Use rollup levels `1m`, `10m`, `30m`, `1h`, `1d`.
- Temperature/humidity/rain/wind speed/wind level use arithmetic average.
- Wind direction angle uses circular mean.
- Vibration keeps the same history response template and current average strategy for now.
- Frontend must not average history points returned by the backend.

---

### Task 1: Backend History Model And Aggregation

**Files:**
- Create: `dam-ai-service/app/services/history_config.py`
- Create: `dam-ai-service/app/services/history_aggregation.py`
- Test: `dam-ai-service/tests/test_history_aggregation.py`

**Interfaces:**
- Produces: `HISTORY_RANGES`, `DEVICE_HISTORY_CONFIG`, `build_history_window(range_key, now_ms=None)`, `aggregate_bucket_values(device_name, values_by_field)`.

- [ ] Add tests for range mapping, circular wind direction mean, and per-device average strategies.
- [ ] Implement config and aggregation helpers.
- [ ] Run: `python3 -m pytest dam-ai-service/tests/test_history_aggregation.py -q`.

### Task 2: IoTDB Rollup And Archive Service

**Files:**
- Create: `dam-ai-service/app/services/sensor_history_service.py`
- Modify: `dam-ai-service/app/services/iotdb_service.py`
- Test: `dam-ai-service/tests/test_sensor_history_service.py`

**Interfaces:**
- Consumes: Task 1 helpers.
- Produces: `sensor_history_service.query_history(device_name, range_key)` and archive export helpers.

- [ ] Add tests using fake IoTDB methods for rollup query fallback and CSV archive row formatting.
- [ ] Implement rollup path naming, bucket writes, rollup query payloads, and raw fallback.
- [ ] Implement raw CSV archive export to the configured local directory.
- [ ] Run: `python3 -m pytest dam-ai-service/tests/test_sensor_history_service.py -q`.

### Task 3: API Integration And Cache Policy

**Files:**
- Modify: `dam-ai-service/app/api/sensor.py`
- Test: `dam-ai-service/tests/test_sensor_history_api.py`

**Interfaces:**
- Consumes: `sensor_history_service.query_history(device_name, range_key)`.
- Produces: stable `/history/{device_name}` response with `rollup_level`, `sample_interval`, and `source`.

- [ ] Add tests for `range=6mo`, invalid device handling, and source metadata.
- [ ] Replace direct IoTDB history logic in the route with the new service.
- [ ] Align cache TTL to selected bucket size.
- [ ] Run: `python3 -m pytest dam-ai-service/tests/test_sensor_history_api.py -q`.

### Task 4: Frontend History Normalization

**Files:**
- Modify: `dam-frontend/src/utils/sensorHistory.js`
- Modify: monitor sensor pages for `6mo` where needed.
- Test: `dam-frontend/src/utils/sensorHistory.test.mjs`

**Interfaces:**
- Consumes: backend `sample_interval`, `window`, and chart-ready history data.
- Produces: frontend series with missing buckets filled as `null`, without averaging multiple backend points.

- [ ] Add JS tests proving returned bucket values are not averaged again.
- [ ] Add `6mo` range config.
- [ ] Update monitor pages to show the new range option.
- [ ] Run: `node dam-frontend/src/utils/sensorHistory.test.mjs`.

### Task 5: Verification

**Files:**
- Existing backend and frontend files touched by previous tasks.

- [ ] Run backend history tests: `python3 -m pytest dam-ai-service/tests/test_history_aggregation.py dam-ai-service/tests/test_sensor_history_service.py dam-ai-service/tests/test_sensor_history_api.py -q`.
- [ ] Run existing IoTDB history tests: `python3 -m pytest dam-ai-service/tests/test_iotdb_history.py -q`.
- [ ] Run frontend history utility tests if Node is available: `node dam-frontend/src/utils/sensorHistory.test.mjs`.
- [ ] Run `git diff --check`.

