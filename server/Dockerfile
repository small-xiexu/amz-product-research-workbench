FROM python:3.12-slim

WORKDIR /app

# 先装依赖（利用缓存）
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

# 复制后端可复用的源码
COPY packages /app/packages
COPY server /app/server

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
