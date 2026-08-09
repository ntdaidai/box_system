# YOLO26x 默认模型检测服务

基于当前服务目录内的未训练/默认预训练权重：

```text
yolo26x.pt
```

服务输出强制归一为三类：

```text
0 boat
1 swimmer
2 person
```

注意：默认 `yolo26x.pt` 是 COCO 模型，原始 COCO 类别里有 `person` 和 `boat`，没有 `swimmer`。因此本服务会做如下映射：

```text
COCO person(0) -> person(2)
COCO boat(8)   -> boat(0)
其他 COCO 类别 -> 过滤
```

`swimmer` 作为服务类别保留，但默认 COCO 模型不会直接输出该类。

## 本地启动

```bash
cd /home/jetson/cp/yolo26x-default
MODEL_WEIGHTS=/home/jetson/cp/night_model/yolo26x.pt \
uvicorn app.main:app --host 0.0.0.0 --port 8013
```

如果本地启动时希望直接使用服务目录里的模型：

```bash
cd /home/jetson/cp/yolo26x-default
MODEL_WEIGHTS=/home/jetson/cp/yolo26x-default/yolo26x.pt \
uvicorn app.main:app --host 0.0.0.0 --port 8013
```

## Docker 启动

```bash
cd /home/jetson/cp/yolo26x-default
docker compose up -d --build
```

服务端口默认映射为 `8013:8000`。

## 接口

```text
GET  /health
GET  /model/info
POST /detect/image
POST /detect/video
POST /infer
POST /predict
```
