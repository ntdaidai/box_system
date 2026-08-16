#!/bin/bash
# 注册 Qwen3.5-35B 本地代理服务到模型库

MODEL_LIBRARY_URL="http://localhost:5001"

# 1. 注册模型
echo "=== 注册模型 ==="
curl -s -X POST "$MODEL_LIBRARY_URL/api/model-registry" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Qwen3.5-35B 云端增强推理",
    "description": "本地代理转发到云端 10.196.85.11:9457，支持灾害评估报告生成",
    "framework": "vLLM",
    "architecture": "Transformer",
    "model_type": "LLM",
    "model_size": "35B"
  }'

echo ""

# 2. 获取模型 ID
MODEL_ID=$(curl -s "$MODEL_LIBRARY_URL/api/model-registry" | python3 -c "
import sys, json
data = json.load(sys.stdin)['data']
for m in data:
    if 'Qwen3.5-35B' in m['name']:
        print(m['id'])
        break
")

if [ -z "$MODEL_ID" ]; then
  echo "错误：未找到模型"
  exit 1
fi

echo "模型 ID: $MODEL_ID"

# 3. 绑定镜像
echo "=== 绑定镜像 ==="
curl -s -X POST "$MODEL_LIBRARY_URL/api/model-registry/$MODEL_ID/bind-image" \
  -H "Content-Type: application/json" \
  -d '{
    "image_name": "qwen35b-proxy:latest",
    "container_port": 9457,
    "host_port": 9457,
    "inference_path": "/infer",
    "health_check_url": "/health",
    "extra_env": {
      "CLOUD_URL": "http://10.196.85.11:9458",
    "INFERENCE_PATH": "/infer"
    },
    "container_config": {
      "network_mode": "host"
    }
  }'

echo ""
echo "=== 注册完成 ==="
