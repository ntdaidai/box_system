#!/bin/bash
# Qwen-VL-4B 本地推理服务 - 模型库注册脚本

MODEL_REGISTRY_URL="${MODEL_REGISTRY_URL:-http://localhost:5001}"
MODEL_NAME="Qwen-VL-4B 本地推理"

echo "正在注册 ${MODEL_NAME} 服务到模型库..."

# 注册模型信息
RESPONSE=$(curl -s -X POST "${MODEL_REGISTRY_URL}/api/model-registry" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "'"${MODEL_NAME}"'",
    "framework": "vLLM",
    "architecture": "Transformer",
    "model_type": "VLM",
    "model_size": "4B",
    "description": "边缘侧灾害巡查智能分析模型，支持多模态输入（图像+文本）"
  }')

echo "$RESPONSE"

# 提取模型 ID
MODEL_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('data', {}).get('id', ''))" 2>/dev/null)

if [ -z "$MODEL_ID" ]; then
    echo "错误：无法获取模型 ID"
    exit 1
fi

echo "模型 ID: ${MODEL_ID}"

# 绑定镜像配置
echo "正在绑定镜像配置..."
curl -s -X POST "${MODEL_REGISTRY_URL}/api/model-registry/${MODEL_ID}/bind-image" \
  -H "Content-Type: application/json" \
  -d '{
    "image_name": "qwen4b-local:latest",
    "container_port": 9901,
    "host_port": 9901,
    "inference_path": "/infer",
    "health_check_url": "/health",
    "extra_env": {
      "VLLM_BASE_URL": "http://localhost:8001",
      "MODEL_NAME": "qwen4B",
      "MAX_TOKENS": "2048",
      "TEMPERATURE": "0.15",
      "UPLOAD_MEDIA_TO_CLOUD": "true",
      "STRICT_MEDIA_UPLOAD": "false",
      "EDGE_MINIO_ENDPOINT": "localhost:9000",
      "EDGE_MINIO_ACCESS_KEY": "minioadmin",
      "EDGE_MINIO_SECRET_KEY": "minioadmin",
      "EDGE_MINIO_SECURE": "false",
      "EDGE_MINIO_BUCKET": "dam",
      "CLOUD_MINIO_ENDPOINT": "10.196.85.11:9469",
      "CLOUD_MINIO_ACCESS_KEY": "minioadmin",
      "CLOUD_MINIO_SECRET_KEY": "minioadmin",
      "CLOUD_MINIO_SECURE": "false",
      "CLOUD_MINIO_BUCKET": "cloud-tasks",
      "CLOUD_MEDIA_PREFIX": "workflow-media"
    }
  }'

echo ""
echo "========================================="
echo "注册完成！"
echo "========================================="
echo "模型 ID:     ${MODEL_ID}"
echo "服务地址:    http://localhost:9901"
echo "健康检查:    http://localhost:9901/health"
echo "推理接口:    POST http://localhost:9901/infer"
echo "========================================="
