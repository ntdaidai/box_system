FROM python:3.10-slim

WORKDIR /app

# 使用清华镜像源安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用代码
COPY app/ ./app/

# 暴露端口
EXPOSE 9901

# 启动服务
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9901"]
