# Redis Docker 部署方案 (Jetson AGX)

## 环境信息
- 平台：NVIDIA Jetson AGX (aarch64)
- 系统版本：JetPack R36.5.0
- Docker：29.5.2

## 目录结构

```
redis/
├── docker-compose.yml    # Docker Compose 配置
├── conf/
│   └── redis.conf        # Redis 自定义配置
├── data/                 # 数据持久化目录
├── logs/                 # 日志目录
└── readme.md             # 本文档
```

## 快速开始

### 1. 启动服务

```bash
docker pull docker.xuanyuan.me/library/redis:7-alpine
cd /home/jetson/redis
docker compose up -d
```

### 2. 验证运行状态

```bash
# 查看容器状态
docker compose ps

# 查看日志
docker compose logs -f redis

# 进入 Redis CLI
docker exec -it redis-server redis-cli
```

### 3. 连接 Redis

```bash
# 本地连接
redis-cli -h 127.0.0.1 -p 6379

# 远程连接（确保防火墙开放 6379 端口）
redis-cli -h <AGX_IP> -p 6379

# 测试连接
redis-cli ping
# 返回 PONG 表示连接成功
```

## 常用操作

### 启停服务

```bash
# 启动
docker compose up -d

# 停止
docker compose down

# 重启
docker compose restart redis

# 查看日志
docker compose logs -f redis
```

### 数据操作

```bash
# 进入 Redis CLI
docker exec -it redis-server redis-cli

# 设置键值
SET mykey "Hello Redis"

# 获取键值
GET mykey

# 查看所有键
KEYS *

# 删除键
DEL mykey

# 查看服务器信息
INFO server

# 查看内存使用
INFO memory
```

### 数据备份

```bash
# 触发 RDB 备份
docker exec redis-server redis-cli BGSAVE

# 备份 RDB 文件
docker cp redis-server:/data/dump.rdb ./backup_$(date +%Y%m%d).rdb
```

### 数据恢复

```bash
# 停止 Redis
docker compose down

# 复制备份文件到数据目录
cp ./backup.rdb ./data/dump.rdb

# 重启 Redis
docker compose up -d
```

### 修改配置

1. 编辑 `conf/redis.conf`
2. 重启容器使配置生效：
   ```bash
   docker compose restart redis
   ```

## 配置说明

### redis.conf 关键参数

| 参数 | 当前值 | 说明 |
|------|--------|------|
| `maxmemory` | 1gb | 最大内存限制 |
| `maxmemory-policy` | allkeys-lru | 内存淘汰策略 |
| `appendonly` | yes | 启用 AOF 持久化 |
| `appendfsync` | everysec | AOF 同步策略 |
| `save` | 900 1 300 10 60 10000 | RDB 快照规则 |
| `bind` | 0.0.0.0 | 监听地址 |
| `port` | 6379 | 监听端口 |

### 内存淘汰策略说明

| 策略 | 说明 |
|------|------|
| `noeviction` | 不淘汰，内存满时返回错误 |
| `allkeys-lru` | 从所有键中淘汰最近最少使用的 |
| `volatile-lru` | 从有过期时间的键中淘汰最近最少使用的 |
| `allkeys-random` | 从所有键中随机淘汰 |
| `volatile-random` | 从有过期时间的键中随机淘汰 |
| `volatile-ttl` | 淘汰即将过期的键 |

### 资源限制

- 内存限制：1GB（可在 docker-compose.yml 中调整）
- AGX 拥有 32GB 内存，可根据实际需求调整

## 安全建议

1. **设置密码**：在 `redis.conf` 中配置 `requirepass`
2. **限制远程访问**：如仅本地使用，可绑定 127.0.0.1
3. **定期备份**：建议配置定时备份任务
4. **更新镜像**：定期更新 Redis 镜像以获取安全补丁

```yaml
# 仅允许本地访问
ports:
  - "127.0.0.1:6379:6379"
```

### 配置密码

```bash
# 在 redis.conf 中添加
requirepass your_strong_password_here

# 连接时需要密码
redis-cli -h 127.0.0.1 -p 6379 -a your_strong_password_here
```

## 故障排查

### 查看详细日志

```bash
docker compose logs redis
```

### 进入容器调试

```bash
docker exec -it redis-server sh
```

### 检查数据目录权限

```bash
ls -la /home/jetson/redis/data/
# 确保 redis 用户有读写权限
```

### 检查内存使用

```bash
docker exec -it redis-server redis-cli INFO memory
```

### 重置数据

```bash
# 停止容器
docker compose down

# 删除数据目录（⚠️ 会丢失所有数据）
sudo rm -rf /home/jetson/redis/data/*

# 重新启动
docker compose up -d
```

## 相关链接

- [Redis 官方文档](https://redis.io/documentation)
- [Redis Docker Hub](https://hub.docker.com/_/redis)
- [Redis GitHub](https://github.com/redis/redis)

## 注意事项

- **aarch64 兼容性**：Redis 7 Alpine 镜像已支持 arm64 架构，可直接使用
- **性能优化**：AGX 拥有 32GB 内存，可根据实际需求调整 `maxmemory`
- **数据持久化**：已启用 RDB + AOF 双重持久化，确保数据安全
- **内存管理**：默认使用 allkeys-lru 策略，内存满时自动淘汰旧数据
