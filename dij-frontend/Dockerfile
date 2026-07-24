# 构建阶段
FROM node:18-alpine as builder

WORKDIR /app

# 设置 yarn 镜像源
RUN yarn config set registry https://registry.npmmirror.com/

# 复制依赖文件
COPY package*.json ./
COPY yarn.lock ./

# 安装依赖
RUN yarn install --network-timeout 600000

# 复制源码
COPY . .

# 设置环境变量
ENV VITE_APP_ENVIRONMENT=production
ENV VITE_APP_APIGATEWAY_BACKEND_HOST=''

# 构建生产版本
RUN yarn build

# 运行阶段 - 只输出构建产物
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
