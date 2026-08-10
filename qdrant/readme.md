# Qdrant Docker 部署方案 (Jetson AGX)

## 环境信息

- 平台：NVIDIA Jetson AGX (aarch64)
- 镜像：`swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/qdrant/qdrant:v1.16.3-linuxarm64`
- HTTP API：`http://127.0.0.1:6333`
- gRPC：`127.0.0.1:6334`

## 目录结构

```text
qdrant/
├── docker-compose.yml
├── data/        # 向量数据持久化目录
├── snapshots/   # 快照目录
└── readme.md
```

## 快速启动

```bash
cd /home/jetson/box_system/qdrant
docker compose up -d
```

也可以从总 Compose 启动：

```bash
cd /home/jetson/box_system
docker compose up -d qdrant
```

## 验证

```bash
curl http://127.0.0.1:6333/
curl http://127.0.0.1:6333/collections
```

## 常用操作

```bash
docker compose ps
docker compose logs -f qdrant
docker compose restart qdrant
```
