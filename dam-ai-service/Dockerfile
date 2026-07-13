FROM docker.m.daocloud.io/library/python:3.10-slim

WORKDIR /app

# 安装系统依赖（MySQL 客户端库 + 串口通信 + 编译工具以支持 psutil 等 C 扩展）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libusb-1.0-0 \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8090

# 启动服务（root 用户以支持串口访问）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
