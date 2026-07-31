# MobileNetV4 灾害分类 API 服务

基于 MobileNetV4 Conv Medium 微调模型的自然灾害分类服务。

## 说明

自然灾害四分类微调模型，测试集 top1 为 92.25%。

## 接口

- `GET /health`：健康检查
- `GET /model/info`：模型信息
- `POST /classify/image`：从 MinIO 获取单张图片并分类
- `POST /classify/video`：从 MinIO 获取视频，按间隔抽帧分类

## 启动

```bash
cd /home/jetson/box_system/models/mobilenetv4-cls
docker-compose build
docker-compose up -d
```

服务默认映射端口：`8006`。

## 图片分类示例

```bash
curl -X POST http://localhost:8006/classify/image \
  -H "Content-Type: application/json" \
  -d '{"bucket": "images", "object_key": "test.jpg"}'
```

## 视频分类示例

```bash
curl -X POST http://localhost:8006/classify/video \
  -H "Content-Type: application/json" \
  -d '{"bucket": "videos", "object_key": "test.mp4", "frame_interval": 30}'
```
