FROM docker.m.daocloud.io/library/python:3.10-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码
COPY . .

# 暴露端口
EXPOSE 5001

# 启动服务
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5001"]
