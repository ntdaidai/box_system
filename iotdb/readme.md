# IoTDB Docker 部署方案 (Jetson AGX)

## 环境信息
- 平台：NVIDIA Jetson AGX (aarch64)
- 系统版本：JetPack R36.5.0
- Docker：29.5.2
- IoTDB 版本：2.0.8-standalone

## 目录结构

```
iotdb/
├── docker-compose-standalone.yml   # Docker Compose 配置
├── data/                           # 数据持久化目录
│   ├── confignode/                 # 配置节点数据
│   └── datanode/                   # 数据节点数据
├── logs/                           # 日志目录
└── readme.md                       # 本文档
```

## 快速开始

### 1. 创建 Docker 网络

```bash
docker network create --driver bridge --subnet 172.18.0.0/16 --gateway 172.18.0.1 iotdb
```

### 2. 拉取镜像

```bash
docker pull apache/iotdb:2.0.8-standalone
```

### 3. 启动服务

```bash
cd /home/jetson/iotdb && docker compose -f docker-compose-standalone.yml up -d
```

### 4. 验证运行状态

```bash
# 查看容器状态
docker compose -f docker-compose-standalone.yml ps

# 查看日志
docker compose -f docker-compose-standalone.yml logs -f

# 进入 IoTDB CLI
docker exec -it iotdb-service /iotdb/sbin/start-cli.sh -h iotdb-service
```

## 端口说明

| 端口 | 用途 | 协议 |
|------|------|------|
| 6667 | IoTDB RPC 端口（客户端连接） | TCP |
| 8080 | REST API（可选，Python/Flink 使用） | HTTP |

## 常用操作

### 启停服务

```bash
# 启动
cd /home/jetson/iotdb
docker compose -f docker-compose-standalone.yml up -d

# 停止
docker compose -f docker-compose-standalone.yml down

# 重启
docker compose -f docker-compose-standalone.yml restart

# 查看日志
docker compose -f docker-compose-standalone.yml logs -f
```

### 使用 IoTDB CLI

```bash
# 进入 CLI
docker exec -it iotdb-service /iotdb/sbin/start-cli.sh -h iotdb-service

# 常用 SQL 示例
show databases;
show timeseries;
select * from root.sg1.d1 limit 10;
```

### 使用 REST API

```bash
# 查询数据（需先创建时间序列）
curl -X POST http://localhost:8080/rest/v2/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "show databases"}'
```

### 数据备份

```bash
# 备份数据目录
tar -czvf iotdb_backup_$(date +%Y%m%d).tar.gz /home/jetson/iotdb/data/

# 使用 CLI 导出
docker exec iotdb-service /iotdb/sbin/start-cli.sh -h iotdb-service -e "export data to '/tmp/backup'"
```

## 配置说明

### docker-compose-standalone.yml 关键配置

| 配置项 | 当前值 | 说明 |
|--------|--------|------|
| `image` | apache/iotdb:2.0.8-standalone | IoTDB 镜像版本（aarch64 兼容） |
| `restart` | always | 崩溃自动重启 |
| `TZ` | Asia/Shanghai | 时区设置 |
| `cn_internal_address` | iotdb-service | ConfigNode 内部通信地址 |
| `cn_internal_port` | 10710 | ConfigNode 内部端口 |
| `cn_consensus_port` | 10720 | ConfigNode 共识端口 |
| `dn_rpc_address` | iotdb-service | DataNode RPC 地址 |
| `dn_rpc_port` | 6667 | DataNode RPC 端口 |
| `dn_mpp_data_exchange_port` | 10740 | MPP 数据交换端口 |
| `dn_schema_region_consensus_port` | 10750 | Schema Region 共识端口 |
| `dn_data_region_consensus_port` | 10760 | Data Region 共识端口 |

### 健康检查

```yaml
healthcheck:
  test: ["CMD-SHELL", "/iotdb/sbin/start-cli.sh -h iotdb-service -e 'SHOW VERSION' || exit 1"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 60s    # IoTDB 冷启动较慢，给予充足初始化时间
```

### 网络配置

- 使用外部 bridge 网络 `iotdb`
- 固定 IP：`172.18.0.6`
- 子网：`172.18.0.0/16`

## 安全建议

1. **限制远程访问**：如仅本地使用，可绑定 `127.0.0.1`
   ```yaml
   ports:
     - "127.0.0.1:6667:6667"
     - "127.0.0.1:8080:8080"
   ```
2. **定期备份**：建议配置定时备份任务
3. **更新镜像**：定期更新 IoTDB 镜像以获取安全补丁

## 故障排查

### 查看详细日志

```bash
# 实时日志
docker compose -f docker-compose-standalone.yml logs -f

# 查看错误日志
tail -f /home/jetson/iotdb/logs/*error*.log
```

### 进入容器调试

```bash
docker exec -it iotdb-service bash
```

### 检查数据目录权限

```bash
ls -la /home/jetson/iotdb/data/
```

### 检查网络连接

```bash
# 查看网络配置
docker network inspect iotdb

# 测试端口连通性
nc -zv localhost 6667
nc -zv localhost 8080
```

### 重置数据

```bash
# 停止容器
docker compose -f docker-compose-standalone.yml down

# 删除数据目录（⚠️ 会丢失所有数据）
sudo rm -rf /home/jetson/iotdb/data/*

# 重新启动
docker compose -f docker-compose-standalone.yml up -d
```

## 性能优化

### 资源限制

在 `docker-compose-standalone.yml` 中添加资源限制：

```yaml
deploy:
  resources:
    limits:
      memory: 8G      # AGX 有 32GB 内存，可适当分配
      cpus: '4'        # 限制 CPU 核心数
```

### IoTDB 内存配置

IoTDB 默认使用 JVM，可通过环境变量调整堆内存：

```yaml
environment:
  - MAX_HEAP_SIZE=4G
  - HEAP_NEWSIZE=1G
```

## 注意事项

- **aarch64 兼容性**：`apache/iotdb:2.0.8-standalone` 已支持 arm64 架构，可直接使用
- **冷启动时间**：IoTDB 首次启动可能需要 30-60 秒，请耐心等待健康检查通过
- **数据持久化**：数据存储在 `./data` 目录，删除容器不会丢失数据
- **端口冲突**：确保 6667 和 8080 端口未被其他服务占用
- **网络配置**：使用固定 IP 可避免容器重启后 IP 变化的问题

## 相关链接

- [IoTDB 官方文档](https://iotdb.apache.org/UserGuide/latest/)
- [IoTDB Docker Hub](https://hub.docker.com/r/apache/iotdb)
- [IoTDB GitHub](https://github.com/apache/iotdb)
