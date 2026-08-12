# RT-DETR 默认模型检测服务

基于当前服务目录内的原始预训练权重：

```text
rtdetr-x.pt
```

服务输出强制归一为三类：

```text
0 boat
1 swimmer
2 person
```

注意：默认 `rtdetr-x.pt` 是 COCO 模型，原始 COCO 类别里有 `person` 和 `boat`，没有 `swimmer`。因此本服务会做如下映射：

```text
COCO person(0) -> person(2)
COCO boat(8)   -> boat(0)
其他 COCO 类别 -> 过滤
```

`swimmer` 作为服务类别保留，但默认 COCO 模型不会直接输出该类。

## 本地启动

```bash
cd /home/jetson/cp/rtdetr-default
MODEL_WEIGHTS=/home/jetson/cp/rtdetr-default/rtdetr-x.pt \
uvicorn app.main:app --host 0.0.0.0 --port 8015
```

## Docker 启动

```bash
cd /home/jetson/cp/rtdetr-default
docker compose up -d --build
```

服务端口默认映射为 `8015:8000`。

## 接口

```text
GET  /health
GET  /model/info
POST /detect/image
POST /detect/video
POST /infer
POST /predict
```
