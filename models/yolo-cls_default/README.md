# YOLO26x 默认分类模型 API 服务

基于 YOLO26x 默认分类模型的图像分类服务。

## 说明

默认预训练模型，主要用于模型对照或继续微调，不是自然灾害四分类微调模型。

## 接口

- `GET /health`：健康检查
- `GET /model/info`：模型信息
- `POST /classify/image`：从 MinIO 获取单张图片并分类
- `POST /classify/video`：从 MinIO 获取视频，按间隔抽帧分类

## 启动

```bash
cd /home/jetson/box_system/models/yolo-cls_default
docker-compose build
docker-compose up -d
```

服务默认映射端口：`8005`。

## 图片分类示例

```bash
curl -X POST http://localhost:8005/classify/image \
  -H "Content-Type: application/json" \
  -d '{"bucket": "images", "object_key": "test.jpg"}'
```

## 视频分类示例

```bash
curl -X POST http://localhost:8005/classify/video \
  -H "Content-Type: application/json" \
  -d '{"bucket": "videos", "object_key": "test.mp4", "frame_interval": 30}'
```
