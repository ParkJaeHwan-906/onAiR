# ========================================
# YOLO Service Dockerfile
# ========================================

FROM python:3.10-slim

WORKDIR /app

# System dependencies (minimal)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY ai_server/yolo_service/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        torch==2.9.0+cpu \
        torchvision==0.24.0+cpu \
        torchaudio==2.9.0+cpu \
        --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code (retain package structure for shared modules)
COPY ai_server /app/ai_server

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 9000

CMD ["uvicorn", "ai_server.yolo_service.app.main:app", "--host", "0.0.0.0", "--port", "9000"]

