# Qwen3.5-35B 云端增强推理代理

本地代理服务，转发请求到云端 `10.196.85.11:9457`。

## 架构

```
客户端 → 本地代理 (localhost:9457) → 云端服务 (10.196.85.11:9457)
```

## 部署

```bash
# 构建并启动
docker compose up -d

# 验证
curl http://localhost:9457/health
```

## 推理接口

```
POST http://localhost:9457/api/v1/cloud-inference
```

```bash
curl -X POST http://localhost:9457/api/v1/cloud-inference \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task_test_001",
    "media_objects": [{"bucket": "cloud-tasks", "object": "test/images/sample.jpg"}],
    "specialized_result": {"model": "YOLOv26-disaster", "category": "landslide", "confidence": 0.91},
    "sensor_data": {"rainfall_24h": 126.4, "humidity": 91.2, "vibration": 0.83},
    "edge_analysis": {"scene_type": "库区边坡", "risk_level": "medium", "confidence": 0.76, "evidence": ["存在疑似滑移区域"]},
    "report_requirement": {"format": "json", "language": "zh-CN", "report_type": "emergency_assessment"}
  }'
```

## 模型库注册

```bash
bash register.sh
```
