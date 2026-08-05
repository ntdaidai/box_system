# MySQL Docker 部署方案 (Jetson AGX)

## 环境信息
- 平台：NVIDIA Jetson AGX (aarch64)
- 系统版本：JetPack R36.5.0
- Docker：29.5.2

## 目录结构

```
mysql/
├── docker-compose.yml    # Docker Compose 配置
├── conf/
│   └── my.cnf           # MySQL 自定义配置
├── data/                # 数据持久化目录
├── init/
│   └── init.sql         # 初始化 SQL 脚本
├── logs/                # 日志目录
└── readme.md            # 本文档
```

## 快速开始

### 1. 修改密码

编辑 `docker-compose.yml`，将 `your_strong_password_here` 改为你的强密码：

```yaml
environment:
  MYSQL_ROOT_PASSWORD: 你的强密码
```

### 2. 启动服务

```bash
sudo docker pull mysql:8.0
cd /home/jetson/mysql
sudo docker compose up -d
```

### 3. 验证运行状态

```bash
# 查看容器状态
sudo docker compose ps

# 查看日志
sudo docker compose logs -f mysql

# 进入 MySQL 命令行
sudo docker exec -it mysql-server mysql -uroot -p
```

### 4. 连接 MySQL

```bash
# 本地连接
mysql -h 127.0.0.1 -P 3306 -uroot -p

# 远程连接（确保防火墙开放 3306 端口）
mysql -h <AGX_IP> -P 3306 -uroot -p
```

## 常用操作

### 启停服务

```bash
# 启动
sudo docker compose up -d

# 停止
sudo docker compose down

# 重启
sudo docker compose restart mysql

# 查看日志
sudo docker compose logs -f mysql
```

### 数据备份

```bash
# 备份所有数据库
sudo docker exec mysql-server mysqldump -uroot -p --all-databases > backup_$(date +%Y%m%d).sql

# 备份指定数据库
sudo docker exec mysql-server mysqldump -uroot -p dam_system > dam_system_backup_$(date +%Y%m%d).sql
```

### 数据恢复

```bash
# 恢复数据库
sudo docker exec -i mysql-server mysql -uroot -p dam_system < backup.sql
```

### 修改配置

1. 编辑 `conf/my.cnf`
2. 重启容器使配置生效：
   ```bash
   sudo docker compose restart mysql
   ```

## 配置说明

### my.cnf 关键参数

| 参数 | 当前值 | 说明 |
|------|--------|------|
| `innodb_buffer_pool_size` | 2G | InnoDB 缓冲池大小，建议为系统内存的 50-70% |
| `max_connections` | 200 | 最大连接数 |
| `max_allowed_packet` | 64M | 最大数据包大小 |
| `character-set-server` | utf8mb4 | 字符集 |
| `default-time-zone` | +08:00 | 时区设置 |

### 资源限制

- 内存限制：4GB（可在 docker-compose.yml 中调整）
- 如需更多资源，修改 `deploy.resources.limits` 部分

## 安全建议

1. **修改默认密码**：首次部署后立即修改 root 密码
2. **限制远程访问**：如仅本地使用，可删除 ports 映射或绑定 127.0.0.1
3. **定期备份**：建议配置定时备份任务
4. **更新镜像**：定期更新 MySQL 镜像以获取安全补丁

```yaml
# 仅允许本地访问
ports:
  - "127.0.0.1:3306:3306"
```

## 故障排查

### 查看详细日志

```bash
sudo docker compose logs mysql
```

### 进入容器调试

```bash
sudo docker exec -it mysql-server bash
```

### 检查数据目录权限

```bash
ls -la /home/jetson/mysql/data/
# 确保 mysql 用户有读写权限
```

### 重置密码

```bash
# 停止容器
sudo docker compose down

# 删除数据目录（⚠️ 会丢失所有数据）
sudo rm -rf /home/jetson/mysql/data/*

# 重新启动
sudo docker compose up -d
```

## 注意事项

- **aarch64 兼容性**：MySQL 8.0 官方镜像已支持 arm64 架构，可直接使用
- **性能优化**：AGX 拥有 32GB 内存，可根据实际需求调整 `innodb_buffer_pool_size`
- **数据持久化**：数据存储在 `./data` 目录，删除容器不会丢失数据
- **首次启动**：初始化脚本 `init/init.sql` 仅在首次启动时执行
