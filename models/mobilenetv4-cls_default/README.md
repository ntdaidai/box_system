# MobileNetV4 默认分类模型 API 服务

基于 MobileNetV4 Conv Medium 默认预训练模型的图像分类服务。

## 说明

默认预训练模型，输出原始预训练类别编号，主要用于对照或继续微调。

## 接口

- `GET /health`：健康检查
- `GET /model/info`：模型信息
- `POST /classify/image`：从 MinIO 获取单张图片并分类
- `POST /classify/video`：从 MinIO 获取视频，按间隔抽帧分类

## 启动

```bash
cd /home/jetson/box_system/models/mobilenetv4-cls_default
docker-compose build
docker-compose up -d
```

服务默认映射端口：`8007`。

## 图片分类示例

```bash
curl -X POST http://localhost:8007/classify/image \
  -H "Content-Type: application/json" \
  -d '{"bucket": "images", "object_key": "test.jpg"}'
```

## 视频分类示例

```bash
curl -X POST http://localhost:8007/classify/video \
  -H "Content-Type: application/json" \
  -d '{"bucket": "videos", "object_key": "test.mp4", "frame_interval": 30}'
```
