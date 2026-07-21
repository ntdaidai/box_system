#!/bin/bash

# OnlyOffice 快速部署脚本
# 用于 box_system 项目

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 Docker 是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi

    print_success "Docker 和 Docker Compose 已安装"
}

# 检查系统资源
check_resources() {
    print_info "检查系统资源..."

    # 检查内存
    total_memory=$(free -m | awk '/^Mem:/{print $2}')
    if [ "$total_memory" -lt 2048 ]; then
        print_warning "系统内存不足 2GB，OnlyOffice 可能运行不稳定"
    else
        print_success "系统内存充足: ${total_memory}MB"
    fi

    # 检查磁盘空间
    available_space=$(df -m . | awk 'NR==2{print $4}')
    if [ "$available_space" -lt 10240 ]; then
        print_warning "可用磁盘空间不足 10GB，建议清理磁盘空间"
    else
        print_success "可用磁盘空间充足: ${available_space}MB"
    fi
}

# 创建环境配置文件
create_env_file() {
    print_info "创建环境配置文件..."

    if [ ! -f .env.onlyoffice ]; then
        cat > .env.onlyoffice << EOF
# OnlyOffice 配置
ONLYOFFICE_SERVER_URL=http://localhost:8080
ONLYOFFICE_JWT_SECRET=$(openssl rand -hex 32)
DOCUMENT_STORAGE_PATH=/var/www/onlyoffice/Data
VITE_ONLYOFFICE_URL=http://localhost:8080
EOF
        print_success "环境配置文件已创建: .env.onlyoffice"
    else
        print_warning "环境配置文件已存在，跳过创建"
    fi
}

# 启动 OnlyOffice 服务
start_onlyoffice() {
    print_info "启动 OnlyOffice Document Server..."

    # 启动服务
    docker compose up -d onlyoffice-documentserver

    # 等待服务启动
    print_info "等待 OnlyOffice 服务启动..."
    sleep 10

    # 检查服务状态
    max_retries=30
    retry_count=0

    while [ $retry_count -lt $max_retries ]; do
        if curl -s -f http://localhost:8080/healthcheck > /dev/null 2>&1; then
            print_success "OnlyOffice 服务启动成功"
            return 0
        fi

        retry_count=$((retry_count + 1))
        print_info "等待服务就绪... ($retry_count/$max_retries)"
        sleep 5
    done

    print_error "OnlyOffice 服务启动超时"
    print_info "请查看日志: docker logs dam-onlyoffice"
    return 1
}

# 验证服务
verify_service() {
    print_info "验证 OnlyOffice 服务..."

    # 检查健康状态
    health_status=$(curl -s http://localhost:8080/healthcheck)
    if [ "$health_status" = '{"status":"ok"}' ]; then
        print_success "OnlyOffice 健康检查通过"
    else
        print_warning "OnlyOffice 健康检查返回异常: $health_status"
    fi

    # 检查 API 是否可访问
    if curl -s -f http://localhost:8080/web-apps/apps/api/documents/api.js > /dev/null 2>&1; then
        print_success "OnlyOffice API 可访问"
    else
        print_warning "OnlyOffice API 无法访问"
    fi
}

# 启动后端服务
start_backend() {
    print_info "启动后端服务..."

    # 检查后端是否已经运行
    if docker compose ps dam-server-python | grep -q "Up"; then
        print_success "后端服务已在运行"
    else
        docker compose up -d dam-server-python
        print_success "后端服务已启动"
    fi
}

# 启动前端服务
start_frontend() {
    print_info "启动前端服务..."

    # 检查前端是否已经运行
    if docker compose ps dam-frontend | grep -q "Up"; then
        print_success "前端服务已在运行"
    else
        docker compose up -d dam-frontend
        print_success "前端服务已启动"
    fi
}

# 打印访问信息
print_access_info() {
    echo ""
    echo "=========================================="
    echo "  OnlyOffice 集成部署完成！"
    echo "=========================================="
    echo ""
    echo "访问地址："
    echo "  - 前端页面: http://localhost:9457"
    echo "  - 文档管理: http://localhost:9457/document"
    echo "  - OnlyOffice 管理: http://localhost:8080"
    echo "  - 后端 API: http://localhost:8090/docs"
    echo ""
    echo "快速测试："
    echo "  1. 访问 http://localhost:9457/document"
    echo "  2. 点击 '上传文档' 按钮"
    echo "  3. 上传一个 Word 或 Excel 文件"
    echo "  4. 点击 '编辑' 按钮打开文档"
    echo ""
    echo "配置文件："
    echo "  - .env.onlyoffice (OnlyOffice 配置)"
    echo "  - docker-compose.yml (Docker 编排)"
    echo ""
    echo "常用命令："
    echo "  - 查看日志: docker logs -f dam-onlyoffice"
    echo "  - 重启服务: docker compose restart onlyoffice-documentserver"
    echo "  - 停止服务: docker compose down"
    echo ""
}

# 主函数
main() {
    echo "=========================================="
    echo "  OnlyOffice 快速部署脚本"
    echo "=========================================="
    echo ""

    # 切换到项目根目录
    cd "$(dirname "$0")/.."

    # 执行部署步骤
    check_docker
    check_resources
    create_env_file
    start_onlyoffice
    verify_service
    start_backend
    start_frontend
    print_access_info
}

# 执行主函数
main "$@"
