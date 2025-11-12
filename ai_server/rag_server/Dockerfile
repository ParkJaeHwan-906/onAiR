# ========================================
# 🐳 RAG Server Dockerfile (Multi-Stage Build)
# ========================================

# =============== Build Stage ===============
FROM python:3.10-slim AS builder

# 작업 디렉토리 설정
WORKDIR /app

# 빌드에 필요한 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 파일 복사
COPY requirements.txt .

# pip 업그레이드
RUN pip install --no-cache-dir --upgrade pip

# PyTorch CPU 버전 먼저 설치 (리눅스/EC2 환경용)
# requirements.txt에서는 --index-url 옵션을 사용할 수 없으므로 여기서 처리
RUN pip install --no-cache-dir torch==2.9.0+cpu torchvision==0.24.0+cpu torchaudio==2.9.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# 나머지 의존성 설치 (torch 제외)
RUN pip install --no-cache-dir -r requirements.txt

# ✅ ultralytics가 opencv-python을 자동 설치하므로, headless로 덮어씌움
RUN pip uninstall -y opencv-python && \
    pip install --no-cache-dir --force-reinstall opencv-python-headless==4.10.0.84

# ✅ numpy 버전 강제 재설치 (FAISS 호환)
RUN pip install --no-cache-dir --force-reinstall numpy==1.26.4

# =============== Runtime Stage ===============
FROM python:3.10-slim

# 작업 디렉토리 설정
WORKDIR /app

# 런타임에 필요한 시스템 패키지만 설치 (curl은 헬스체크용)
RUN apt-get update && apt-get install -y \
    curl \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# 빌드 스테이지에서 설치된 Python 패키지 복사
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 애플리케이션 코드 복사
COPY app/ ./app/
COPY scripts/ ./scripts/

# credentials 디렉토리 생성 (GCP TTS 키 파일용)
RUN mkdir -p credentials

# 포트 노출
EXPOSE 8000

# 환경변수 설정 (기본값, Jenkins에서 오버라이드 가능)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# uvicorn으로 FastAPI 서버 실행
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["uvicorn", "app.main:asgi_app", "--host", "0.0.0.0", "--port", "8000"]

