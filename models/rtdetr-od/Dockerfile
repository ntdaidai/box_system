# 复用本机已经验证过的 RT-DETR Jetson 运行环境，避免重复安装大体积依赖。
FROM dam-import/rtdetr-od-default:latest

WORKDIR /app

COPY app/ /app/
COPY rtdetr_3_best.pt /app/models/rtdetr_3_best.pt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
