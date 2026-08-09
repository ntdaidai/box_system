# YOLO26x SmallObj-2 检测服务

基于当前服务目录内的 `yolo26x_smallobj_2_best.pt` 封装的 FastAPI 目标检测服务。

类别约定:

```text
0 boat
1 swimmer
2 person
3 crowd
```

## 本地启动

```bash
cd /home/jetson/cp/yolo26x
MODEL_WEIGHTS=/home/jetson/cp/night_model/outputs/yolo26x_smallobj-2/weights/best.pt \
uvicorn app.main:app --host 0.0.0.0 --port 8012
```

如果本地启动时希望直接使用服务目录里的模型：

```bash
cd /home/jetson/cp/yolo26x
MODEL_WEIGHTS=/home/jetson/cp/yolo26x/yolo26x_smallobj_2_best.pt \
uvicorn app.main:app --host 0.0.0.0 --port 8012
```

## Docker 启动

```bash
cd /home/jetson/cp/yolo26x
docker compose up -d --build
```

服务端口默认映射为 `8012:8000`。

## 接口

### 健康检查

```bash
curl http://localhost:8012/health
```

### 模型信息

```bash
curl http://localhost:8012/model/info
```

### 图片检测

```bash
curl -X POST http://localhost:8012/detect/image \
  -H 'Content-Type: application/json' \
  -d '{"bucket":"your-bucket","object_key":"path/to/image.jpg"}'
```

### 视频抽帧检测

```bash
curl -X POST http://localhost:8012/detect/video \
  -H 'Content-Type: application/json' \
  -d '{"bucket":"your-bucket","object_key":"path/to/video.mp4","frame_interval":30}'
```

### 工作流统一入口

兼容 `/infer` 和 `/predict`，会从 payload 中自动查找图片或视频引用。
