#!/bin/bash
# ============================================================
# 轻量级模型库 - 数据库初始化脚本
# 项目：dam-model-library
# 使用方法：./scripts/init_db.sh
# 说明：通过 Docker 容器执行 MySQL 命令创建数据库和表
# ============================================================

# 数据库配置
DB_NAME="model_registry"
DB_USER="root"
DB_PASSWORD="root"
MYSQL_CONTAINER="mysql-server"
SQL_FILE="scripts/init.sql"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# MySQL 执行函数
mysql_exec() {
    docker exec -i "$MYSQL_CONTAINER" mysql -u "$DB_USER" -p"$DB_PASSWORD" "$@"
}

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          轻量级模型库 - 数据库初始化脚本                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 检查 SQL 文件
if [ ! -f "$SQL_FILE" ]; then
    echo -e "${RED}错误: 找不到 ${SQL_FILE} 文件${NC}"
    exit 1
fi

# 检查 MySQL 容器
echo -e "${YELLOW}[0/3] 检查 MySQL 容器状态...${NC}"
if ! docker ps --format '{{.Names}}' | grep -q "^${MYSQL_CONTAINER}$"; then
    echo -e "${RED}错误: MySQL 容器 ${MYSQL_CONTAINER} 未运行${NC}"
    exit 1
fi
echo -e "${GREEN}✓ MySQL 容器运行正常${NC}"

# 检查连接
if ! mysql_exec -e "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${RED}错误: 无法连接到 MySQL${NC}"
    exit 1
fi
echo -e "${GREEN}✓ MySQL 连接成功${NC}"
echo ""

# 创建数据库
echo -e "${GREEN}[1/3] 创建数据库 ${DB_NAME}...${NC}"
mysql_exec -e "CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
if [ $? -ne 0 ]; then
    echo -e "${RED}创建数据库失败${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 数据库创建成功${NC}"

# 执行建表脚本
echo -e "${GREEN}[2/3] 执行建表脚本...${NC}"
mysql_exec "$DB_NAME" < "$SQL_FILE"
if [ $? -ne 0 ]; then
    echo -e "${RED}建表失败${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 建表成功${NC}"

# 验证结果
echo -e "${GREEN}[3/3] 验证结果...${NC}"
echo ""
echo -e "${YELLOW}已创建的表：${NC}"
mysql_exec "$DB_NAME" -e "SHOW TABLES;" 2>/dev/null

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                 ✓ 数据库初始化完成！                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
