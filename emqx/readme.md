# EMQX Docker 部署方案 (Jetson AGX)

## 环境信息

- 平台：NVIDIA Jetson AGX (aarch64)
- 系统版本：JetPack R36.5.0
- Docker：29.5.2
- 镜像：swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/emqx:5.8.8-linuxarm64

## 目录结构

```
emqx/
├── docker-compose.yml    # Docker Compose 配置
├── conf/                 # EMQX 配置目录
├── data/                 # 数据持久化目录
├── log/                  # 日志目录
└── readme.md             # 本文档
```

## 快速开始

### 1. 修改密码

编辑 `docker-compose.yml`，修改 Dashboard 默认密码：

```yaml
environment:
  EMQX_DASHBOARD__DEFAULT_PASSWORD: 你的强密码
```

### 2. 启动服务

```bash
cd /home/jetson/emqx
sudo docker compose up -d
```

### 3. 验证运行状态

```bash
# 查看容器状态
sudo docker compose ps

# 查看日志
sudo docker compose logs -f emqx

# 检查 EMQX 状态
sudo docker exec -it emqx-server /opt/emqx/bin/emqx ctl status
```

### 4. 访问 Dashboard

浏览器打开：`http://<AGX_IP>:18083`

- 默认用户名：`admin`
- 默认密码：`public`（或你在 docker-compose.yml 中设置的密码）

## 端口说明

| 端口  | 协议 | 说明                    |
| ----- | ---- | ----------------------- |
| 1883  | TCP  | MQTT 协议               |
| 8883  | TCP  | MQTT SSL/TLS            |
| 8083  | TCP  | MQTT over WebSocket     |
| 8084  | TCP  | MQTT over WebSocket SSL |
| 18083 | TCP  | EMQX Dashboard 管理界面 |

## 常用操作

### 启停服务

```bash
# 启动
sudo docker compose up -d

# 停止
sudo docker compose down

# 重启
sudo docker compose restart emqx

# 查看日志
sudo docker compose logs -f emqx
```

### EMQX CLI 命令

```bash
# 查看集群状态
sudo docker exec -it emqx-server /opt/emqx/bin/emqx ctl cluster status

# 查看客户端连接
sudo docker exec -it emqx-server /opt/emqx/bin/emqx ctl clients list

# 查看主题
sudo docker exec -it emqx-server /opt/emqx/bin/emqx ctl topics list

# 查看订阅
sudo docker exec -it emqx-server /opt/emqx/bin/emqx ctl subscriptions list
```

### MQTT 客户端测试

```bash
# 订阅主题（需要安装 mosquitto-clients）
mosquitto_sub -h <AGX_IP> -p 1883 -t "test/topic" -u "admin" -P "你的密码"

# 发布消息
mosquitto_pub -h <AGX_IP> -p 1883 -t "test/topic" -m "Hello EMQX" -u "admin" -P "你的密码"
```

## 配置说明

### 环境变量

| 变量                                 | 默认值    | 说明             |
| ------------------------------------ | --------- | ---------------- |
| `EMQX_NAME`                        | emqx      | 节点名称         |
| `EMQX_HOST`                        | 127.0.0.1 | 节点主机名       |
| `EMQX_DASHBOARD__DEFAULT_USERNAME` | admin     | Dashboard 用户名 |
| `EMQX_DASHBOARD__DEFAULT_PASSWORD` | public    | Dashboard 密码   |

### 资源限制

- 内存限制：4GB（可在 docker-compose.yml 中调整）
- 如需更多资源，修改 `deploy.resources.limits` 部分

## 安全建议

1. **修改默认密码**：首次部署后立即修改 Dashboard 密码
2. **启用 TLS**：生产环境建议配置 SSL/TLS 证书
3. **限制远程访问**：如仅本地使用，可绑定 127.0.0.1
4. **配置认证**：生产环境建议配置数据库认证或 HTTP 认证
5. **定期备份**：建议定期备份 `data` 目录

```yaml
# 仅允许本地访问 Dashboard
ports:
  - "127.0.0.1:18083:18083"
```

## 故障排查

### 查看详细日志

```bash
sudo docker compose logs emqx
```

### 进入容器调试

```bash
sudo docker exec -it emqx-server bash
```

### 检查数据目录权限

```bash
ls -la /home/jetson/emqx/data/
```

### 重置数据

```bash
# 停止容器
sudo docker compose down

# 删除数据目录（⚠️ 会丢失所有数据）
sudo rm -rf /home/jetson/emqx/data/*

# 重新启动
sudo docker compose up -d
```

## 注意事项

- **aarch64 兼容性**：使用 `emqx:5.8.8-linuxarm64` 专为 ARM64 架构构建
- **性能优化**：AGX 拥有 32GB 内存，可根据实际需求调整资源限制
- **数据持久化**：数据存储在 `./data` 目录，删除容器不会丢失数据
- **首次启动**：首次启动可能需要 30-60 秒初始化
