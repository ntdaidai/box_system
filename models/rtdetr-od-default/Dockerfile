# 基础镜像（Jetson 优化）
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/dustynv/l4t-pytorch:r36.4.0-linuxarm64

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 依赖单独成层：只有 requirements.txt 变化时才重新安装；固定版本并优先使用 ARM64 wheel。
# 当前模型库通过 Docker API 使用 legacy builder，因此不使用 BuildKit 专属的 cache mount。
RUN python3 -m pip install \
      --no-cache-dir \
      --prefer-binary \
      --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
      -r requirements.txt \
    && python3 -m pip install \
      --no-deps \
      --no-cache-dir \
      --prefer-binary \
      --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
      ultralytics==8.4.120

COPY app/ /app/

RUN mkdir -p /app/models
COPY rtdetr-x.pt /app/models/rtdetr-x.pt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
