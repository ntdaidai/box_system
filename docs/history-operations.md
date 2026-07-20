# 传感器历史模块运行手册

## 数据边界

- IoTDB `root.dam.sensor.*` 是在线原始事实源。
- `/app/data/sensor_pending.sqlite3` 是原始写入前的本地 WAL 队列；只有 IoTDB 确认写入后才删除。
- IoTDB `root.dam.rollup_*` 是可重建的查询加速层。
- `/app/data/archive/sensors/YYYY-MM-DD` 是长期原始 CSV 补充副本。
- Redis 与浏览器缓存不是数据源，不得用于判断历史数据是否存在。

## 时间粒度

| 查询范围 | rollup | 桶大小 |
| --- | --- | --- |
| 1 小时 | 1m | 1 分钟 |
| 6 小时 | 10m | 10 分钟 |
| 1 天 | 30m | 30 分钟 |
| 7 天 | 1h | 1 小时 |
| 6 个月 | 1d | 1 个 Asia/Shanghai 自然日 |

长范围重建按 `1d ← 1h ← 30m ← 10m ← 1m ← raw` 分层读取，禁止在请求中扫描数月秒级原始数据。

## 温湿度趋势

- 近 24 小时读取 `30m` 聚合层，固定最多 48 个时间桶，温度和湿度均使用桶内平均值。
- 年/月视图只读取 `1d` 聚合层，保存每日最高/最低温度、每日最高/最低湿度及有效样本数。
- 旧 CSV 归档由维护线程每分钟回填一天日极值，回填进度写入当日 `_SUCCESS` 的 `temp_extrema_schema`。
- `GET /api/v1/sensor/history/temp-humidity/trends` 使用 Redis 短缓存；前端使用本地缓存立即回显并在后台更新。

## 降水趋势

- 年/月视图只读取 `1d` 聚合层，只向前端提供 `daily_rain` 逐日雨量；不提供预测数据或累计模式。
- 雨量计的 `today_rain` 是自然日内不断增长并在午夜清零的值，日聚合取当天最大观测值，不能取日内平均值。
- 旧 CSV 归档一次最多回填 30 天，进度写入 `_SUCCESS` 的 `rain_daily_schema`，完成后不再重复扫描 CSV。
- `GET /api/v1/sensor/history/rain/trends` 使用 Redis 30 分钟缓存；前端使用本地缓存立即回显并允许读取短期陈旧副本。

## 风速趋势

- 近 24 小时读取 `30m` 聚合层，固定最多 48 个时间桶，使用桶内平均风速、平均风级和圆周平均风向。
- 年/月视图读取 `1d` 聚合层，展示每日平均风速；悬浮详情同时提供风级和主导风向。
- 月视图横轴按日期附带每日主导风向，年视图按月份显示整年趋势。
- `GET /api/v1/sensor/history/wind/trends` 使用 Redis 短缓存；前端使用本地缓存立即回显并在后台更新。

## 振动 RMS

- 新采集的振动记录同时保存原始三轴字段和实时处理器输出的 `total_rms`，历史曲线与实时指标采用同一计算结果。
- 旧记录没有 `total_rms` 时，接口从三轴振动幅值兼容推导，避免历史迁移期间出现断档。
- `GET /api/v1/sensor/vibration/trends` 使用上述统一窗口和 rollup 层，支持 `1h / 6h / 1d / 7d / 6mo`。
- `time` 和 `timestamp` 是 IoTDB 保留时间列，写入层会从测量字段中强制过滤，防止待写队列被坏记录阻塞。

## 健康检查

```bash
python /app/scripts/check_history_health.py
```

Docker 每 30 秒执行一次同样的检查。失败条件：

- 任一设备原始数据超过 120 秒未更新；
- IoTDB 历史查询不可用；
- 最老待写记录超过 120 秒；
- 任一 rollup 层落后超过 10 个桶。

详细状态接口：`GET /api/v1/sensor/history/status`。

重点字段：`pending_queue.oldest_age_seconds`、`history_storage.devices`、`rollup_lag` 和 `archive.pending_days`。

## 故障恢复

1. IoTDB 临时不可用时，原始记录继续进入 SQLite WAL。
2. 后端重启后从同一 WAL 恢复，按设备与原时间戳幂等重放。
3. IoTDB 恢复后队列自动排空，无需人工导入。
4. rollup 检查点保存在 `/app/data/history_state.json`，重启后限速追赶遗漏桶。
5. 归档只有在四个 CSV 原子落盘且四层 rollup 写入成功后才生成 `_SUCCESS`。
6. 存在未完成归档时，禁止清理 IoTDB 原始数据。

## 验证命令

```bash
cd /app
PYTHONPATH=/app python tests/test_durable_sensor_queue.py
PYTHONPATH=/app python tests/test_iotdb_history.py
PYTHONPATH=/app python tests/test_sensor_history_service.py
PYTHONPATH=/app python tests/test_sensor_history_api.py
PYTHONPATH=/app python tests/test_history_aggregation.py
PYTHONPATH=/app python tests/test_history_health.py
```

前端执行 `sensorHistory`、`localResponseCache`、`sensorDetailStartup` 三组脚本测试，并执行 `npm run build`。
