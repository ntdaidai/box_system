# dai
# Jetson-compatible PyTorch/CUDA base. The previous slim image caused pip to
# download a generic CUDA toolchain that was not the device's JetPack runtime.
ARG JETSON_AI_BASE=ghcr.nju.edu.cn/nvidia-ai-iot/vllm:latest-jetson-orin
FROM ${JETSON_AI_BASE}

WORKDIR /app

# 安装系统依赖（基础镜像已包含 Jetson PyTorch、CUDA 与编译工具）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8090

# 启动服务（root 用户以支持串口访问）
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-8090}"]
