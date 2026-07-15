FROM ghcr.io/nvidia-ai-iot/vllm:latest-jetson-orin

# 设置时区
ENV TZ=Asia/Shanghai
# 忽略 UserWarning 警告
ENV PYTHONWARNINGS="ignore::UserWarning"

# 声明模型挂载点
VOLUME /models
# 声明 vllm 缓存挂载点
VOLUME /root/.cache/vllm

# 暴露 OpenAI API 默认端口
EXPOSE 8000

# 启动 vLLM OpenAI API 服务
ENTRYPOINT ["python3", "-m", "vllm.entrypoints.openai.api_server"]
CMD ["--model", "/models", \
     "--served-model-name", "qwen", \
     "--gpu-memory-utilization", "0.5", \
     "--max-model-len", "8192", \
     "--max-num-seqs", "3", \
     "--max-num-batched-tokens", "8192", \
     "--trust-remote-code", \
     "--kv-cache-dtype", "auto", \
     "--enable-prefix-caching", \
     "--generation-config", "vllm", \
     "--tensor-parallel-size", "1"]
