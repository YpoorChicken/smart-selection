# 华普智选 · 前端多阶段镜像
# 第一阶段：Node 构建；第二阶段：nginx 托管静态资源并反代 /api

# ========== Stage 1: build ==========
FROM node:20-alpine AS build

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

COPY frontend/ .
# 浏览器走同源 /api，由 nginx 转发到后端
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# ========== Stage 2: nginx ==========
FROM nginx:1.27-alpine AS runtime

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -qO- http://127.0.0.1/healthz >/dev/null || exit 1
