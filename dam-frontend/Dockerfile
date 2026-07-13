# Vite 开发服务器模式 — 源码通过卷挂载，修改后重启容器即可生效
FROM docker.m.daocloud.io/library/node:18-alpine
WORKDIR /app

# 安装依赖（源码挂载后，node_modules 由卷保留）
COPY package.json ./
RUN npm install --registry=https://registry.npmmirror.com

EXPOSE 9457
CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "9457"]
