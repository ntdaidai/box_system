# RT-DETR rtdetr-3 检测服务

基于当前服务目录内的 `rtdetr_3_best.pt` 封装的 FastAPI 目标检测服务。

类别约定:

```text
0 boat
1 swimmer
2 person
3 crowd
```

## 本地启动

```bash
cd /home/jetson/cp/rtdetr
MODEL_WEIGHTS=/home/jetson/cp/rtdetr/rtdetr_3_best.pt \
uvicorn app.main:app --host 0.0.0.0 --port 8014
```

## Docker 启动

```bash
cd /home/jetson/cp/rtdetr
docker compose up -d --build
```

服务端口默认映射为 `8014:8000`。

## 接口

```text
GET  /health
GET  /model/info
POST /detect/image
POST /detect/video
POST /infer
POST /predict
```
