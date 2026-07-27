#!/bin/bash
# ============================================================
# 大坝监测系统 - MySQL 数据库初始化脚本
# 项目：box_system (dam-ai-service)
# 使用方法：./run_sql.sh
# 说明：通过Docker容器执行MySQL命令
# ============================================================

# 数据库配置
DB_NAME="dam_system"
DB_USER="root"
DB_PASSWORD="root"
MYSQL_CONTAINER="mysql-server"
SQL_FILE="database.sql"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# MySQL执行函数（通过Docker）
mysql_exec() {
    docker exec -i "$MYSQL_CONTAINER" mysql -u "$DB_USER" -p"$DB_PASSWORD" "$@"
}

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          大坝监测系统 - ECA数据库初始化脚本                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}数据库配置：${NC}"
echo -e "  数据库名:  ${GREEN}${DB_NAME}${NC}"
echo -e "  用户名:    ${GREEN}${DB_USER}${NC}"
echo -e "  容器名称:  ${GREEN}${MYSQL_CONTAINER}${NC}"
echo -e "  SQL文件:   ${GREEN}${SQL_FILE}${NC}"
echo ""

# 检查SQL文件是否存在
if [ ! -f "$SQL_FILE" ]; then
    echo -e "${RED}错误: 找不到 ${SQL_FILE} 文件${NC}"
    echo -e "${RED}请确保文件存在于当前目录${NC}"
    exit 1
fi

# 检查Docker容器是否运行
echo -e "${YELLOW}[0/4] 检查MySQL容器状态...${NC}"
if ! docker ps --format '{{.Names}}' | grep -q "^${MYSQL_CONTAINER}$"; then
    echo -e "${RED}错误: MySQL容器 ${MYSQL_CONTAINER} 未运行${NC}"
    echo -e "${RED}请先启动MySQL服务：${NC}"
    echo -e "${CYAN}  cd /home/jetson/mysql && docker compose up -d${NC}"
    exit 1
fi
echo -e "${GREEN}✓ MySQL容器运行正常${NC}"

# 检查MySQL连接
echo -e "${YELLOW}检查MySQL连接...${NC}"
if ! mysql_exec -e "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${RED}错误: 无法连接到MySQL数据库${NC}"
    echo -e "${RED}请检查容器日志：docker logs ${MYSQL_CONTAINER}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ MySQL连接成功${NC}"
echo ""

# 询问用户确认
read -p "是否继续创建数据库 ${DB_NAME} 并执行SQL脚本？(y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}已取消执行${NC}"
    exit 0
fi

echo ""
echo -e "${GREEN}[1/4] 创建数据库...${NC}"

# 创建数据库
mysql_exec -e "CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

if [ $? -ne 0 ]; then
    echo -e "${RED}创建数据库失败${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 数据库 ${DB_NAME} 创建成功${NC}"

echo -e "${GREEN}[2/4] 复制SQL文件到容器...${NC}"

# 复制SQL文件到容器
docker cp "$SQL_FILE" "${MYSQL_CONTAINER}:/tmp/${SQL_FILE}"

if [ $? -ne 0 ]; then
    echo -e "${RED}复制SQL文件失败${NC}"
    exit 1
fi
echo -e "${GREEN}✓ SQL文件复制成功${NC}"

echo -e "${GREEN}[3/4] 执行SQL建表脚本...${NC}"

# 在容器内执行SQL文件
mysql_exec "$DB_NAME" < "$SQL_FILE"

if [ $? -ne 0 ]; then
    echo -e "${RED}SQL执行失败，请检查错误信息${NC}"
    # 清理临时文件
    docker exec "$MYSQL_CONTAINER" rm -f "/tmp/${SQL_FILE}"
    exit 1
fi
echo -e "${GREEN}✓ 建表脚本执行成功${NC}"

# 清理临时文件
docker exec "$MYSQL_CONTAINER" rm -f "/tmp/${SQL_FILE}"

echo -e "${GREEN}[4/4] 验证执行结果...${NC}"
echo ""
echo -e "${YELLOW}已创建的表：${NC}"
mysql_exec "$DB_NAME" -e "SHOW TABLES;" 2>/dev/null

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                 ✓ 数据库初始化完成！                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
