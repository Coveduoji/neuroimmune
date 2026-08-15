# 后端：FastAPI 薄壳 + prototype 算法内核（运行时 import ../prototype）
# 构建上下文是仓库根目录（docker-compose 里 context: .）
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 先装依赖，利用 Docker 缓存层
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

# 复制代码：backend 与 prototype 必须同级（backend 运行时会 import ../prototype）
COPY backend/ /app/backend/
COPY prototype/ /app/prototype/

# 非 root 运行
RUN useradd --create-home --uid 10001 appuser
USER appuser

WORKDIR /app/backend

# 数据目录（SQLite / JSON 状态 / secret.key 等），用卷挂载持久化
ENV NEUROIMMUNE_DATA_DIR=/data

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
