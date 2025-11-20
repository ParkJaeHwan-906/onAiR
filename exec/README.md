# onAiR 포팅 매뉴얼

## 목차
1. [프로젝트 개요](#프로젝트-개요)
2. [시스템 요구사항](#시스템-요구사항)
3. [환경 설정](#환경-설정)
4. [데이터베이스 설정](#데이터베이스-설정)
5. [Docker 네트워크 설정](#docker-네트워크-설정)
6. [Docker 배포](#docker-배포)
7. [Nginx 설정](#nginx-설정)
8. [Jenkins CI/CD 설정](#jenkins-cicd-설정)
9. [외부 서비스 설정](#외부-서비스-설정)
10. [배포 확인](#배포-확인)

### 주요 구성 요소
- **Frontend**: React 19 + Vite 기반 웹 애플리케이션
- **Backend**: Spring Boot 3.5 REST API + SSE
- **AI Service**: FastAPI 기반 SocketIO (RAG Server)
- **Vision Service**: YOLO 기반 객체 탐지 서비스
- **Raspberry Pi Zero 2W**: 스마트 글래스의 신호 전달

## 시스템 요구사항

### 서버 환경
- **OS**: Ubuntu 20.04 LTS 이상
- **CPU**: 4 Core 이상 (AI 서비스 권장)
- **RAM**: 8GB 이상 (권장: 16GB)
- **Storage**: 50GB 이상 (AI 모델 및 데이터 포함)
- **Network**: 인터넷 연결 필수

### 필수 소프트웨어
- **Docker**: 20.10 이상
- **Docker Compose**: 2.0 이상
- **Nginx**: 1.18 이상 (프록시용)
- **Jenkins**: 2.400 이상 (CI/CD용, 선택사항)
- **Certbot**: SSL 인증서 발급용

## 환경 설정

### 1. Docker 설치
```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```

### 2. Nginx 및 Certbot
Nginx와 Certbot은 Docker 컨테이너로 실행되므로 별도 설치가 필요 없습니다.

## 데이터베이스 설정

### 1. MySQL 컨테이너 실행
```bash
docker run -d \
  --name mysql-container \
  --network onair-network \
  -e MYSQL_ROOT_PASSWORD=your_root_password \
  -e MYSQL_DATABASE=onair \
  -e MYSQL_USER=onair_user \
  -e MYSQL_PASSWORD=your_user_password \
  -v ~/mysql-data:/var/lib/mysql \
  -p 3306:3306 \
  mysql:8.0
```

### 2. Elasticsearch 컨테이너 실행
```bash
docker run -d \
  --name elastic-search \
  --network onair-network \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
  docker.elastic.co/elasticsearch/elasticsearch:8.14.0
```

### 3. Redis 컨테이너 실행
```bash
docker run -d \
  --name redis \
  --network onair-network \
  --restart unless-stopped \
  -v /home/ubuntu/redis-data:/data \
  redis:7-alpine \
  redis-server --appendonly yes
```

### 4. 데이터베이스 초기화
백엔드 실행 시 `data.sql` 파일의 초기 데이터가 자동으로 로드됩니다.

## Docker 네트워크 설정

### 1. Docker 네트워크 생성
```bash
docker network create onair-network
```

### 2. 네트워크 확인
```bash
docker network ls | grep onair-network
```

## Docker 배포

### 1. 프로젝트 클론
```bash
cd /opt
sudo git clone [repository-url] onair
cd onair
```

### 2. 환경 변수 설정
Jenkins Credentials에 다음 값들을 설정하거나, `.env` 파일을 생성합니다:

```env
# Database
SPRING_DB_USERNAME=onair_user
SPRING_DB_PASSWORD=your_user_password

# JWT
JWT_SECRET=your-jwt-secret-key
JWT_ACCESS_TOKEN_EXPIRATION=7200000
JWT_REFRESH_TOKEN_EXPIRATION=432000000

# Company UUID
COMPANY_UUID_EXPIRATION=1800000

# Spring Security
SPRING_SECURITY_USER_NAME=admin
SPRING_SECURITY_USER_PASSWORD=your_security_password

# Frontend
VITE_API_URL=https://onair.ai.kr/api
VITE_SOCKET_URL=wss://onair.ai.kr/ws

# AI Service
JSONL_PATH=/path/to/data.jsonl
FAISS_INDEX_PATH=/path/to/faiss.index
EMB_MODEL_NAME=BAAI/bge-m3
ES_HOST=http://elastic-search:9200
ES_INDEX=samkos
CE_MODEL_NAME=BAAI/bge-reranker-large
GMS_API_KEY=your-gms-api-key
GCP_TTS_CREDENTIALS_PATH=/opt/secrets/tts-key.json

# LiveKit
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret
```

### 3. Docker Compose로 서비스 실행
```bash
# 모든 서비스 빌드 및 실행
docker compose up -d --build

# 특정 서비스만 빌드 및 실행
docker compose up -d --build backend frontend ai_server vision

# Nginx만 실행 (다른 서비스가 이미 실행 중일 때)
docker compose up -d nginx

# 서비스 상태 확인
docker compose ps

# 로그 확인
docker compose logs -f [service-name]
```

### 4. 서비스별 설명

#### Backend (Spring Boot)
- **컨테이너 이름**: `spring`
- **포트**: 8080 (내부)
- **의존성**: MySQL

#### Frontend (React)
- **컨테이너 이름**: `react`
- **포트**: 3000 (내부)
- **빌드 시 환경변수**: `VITE_API_URL`, `VITE_SOCKET_URL`

#### AI Server (FastAPI)
- **컨테이너 이름**: `fastapi`
- **포트**: 8000 (내부)
- **의존성**: Elasticsearch, Redis, YOLO Service
- **볼륨**: GCP TTS 크레덴셜 파일

#### Vision Service (YOLO)
- **컨테이너 이름**: `yolo`
- **포트**: 9000 (내부)

#### Nginx (리버스 프록시)
- **컨테이너 이름**: `nginx`
- **포트**: 80, 443 (외부 노출)
- **볼륨**: 
  - `./nginx:/etc/nginx/conf.d` (설정 파일)
  - `./data/certbot/conf:/etc/letsencrypt` (SSL 인증서)
  - `./data/certbot/www:/var/www/certbot` (Certbot 웹루트)
- **의존성**: backend, frontend, ai_server

#### Certbot (SSL 인증서 관리)
- **이미지**: `certbot/certbot`
- **볼륨**: nginx와 동일한 certbot 볼륨 공유
- **용도**: SSL 인증서 발급 및 갱신

## Nginx 설정

### 1. Nginx 설정 파일 디렉토리 생성
```bash
# 프로젝트 루트에서 실행
mkdir -p nginx
mkdir -p data/certbot/conf
mkdir -p data/certbot/www
```

### 2. Nginx 설정 파일 생성
```bash
nano nginx/default.conf
```

### 3. Nginx 설정 내용
```nginx
# http로 오는 요청을 https로 리다이렉트
server {
    listen 80;
    server_name onair.ai.kr www.onair.ai.kr;
    server_tokens off;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# https 프로토콜(443포트) 처리 블록
server {
    listen 443 ssl;
    server_name onair.ai.kr www.onair.ai.kr;
    server_tokens off;

    # SSL 인증서
    ssl_certificate /etc/letsencrypt/live/onair.ai.kr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/onair.ai.kr/privkey.pem;

    # 로그 파일
    access_log  /var/log/nginx/access.log;
    error_log   /var/log/nginx/error.log debug;

    # Backend API 프록시
    location /api/ {
        proxy_pass  http://spring:8080/;
        proxy_set_header    Host                $http_host;
        proxy_set_header    X-Real-IP           $remote_addr;
        proxy_set_header    X-Forwarded-For     $proxy_add_x_forwarded_for;
    }

    # SSE 프록시
    location /api/sse/ {
        proxy_pass http://spring:8080/sse/;

        # SSE 필수 설정
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_set_header Cache-Control no-cache;

        # 버퍼링 비활성화
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;

        # 타임아웃 설정 (1시간)
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # Frontend 프록시
    location / {
        proxy_pass http://react:3000/;
    }

    # Jenkins 프록시
    location /jenkins/ {
        proxy_pass http://jenkins:8080/jenkins/;
        proxy_http_version 1.1;
        proxy_request_buffering off;

        # 기본 헤더
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_set_header X-Forwarded-Proto https;

        # 리다이렉트 재작성
        proxy_redirect http:// https://;

        # 버퍼링 비활성화
        proxy_buffering off;
        proxy_cache off;
    }

    # AI Server 프록시
    location /ai/ {
        proxy_pass http://fastapi:8000/;
    }

    # WebSocket 프록시 (FastAPI SocketIO)
    location /ws/ {
        proxy_pass http://fastapi:8000/ws/;
        proxy_http_version 1.1;

        # WebSocket 업그레이드 필수
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 기본 헤더
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Socket.IO 타임아웃 설정
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
```

**참고**: Docker 네트워크 내에서는 컨테이너 이름으로 통신하므로:
- `backend` → `spring` (컨테이너 이름)
- `frontend` → `react` (컨테이너 이름)
- `ai_server` → `fastapi` (컨테이너 이름)

### 4. Nginx 컨테이너 실행
```bash
# docker-compose.yml에 nginx 서비스가 포함되어 있으므로
docker compose up -d nginx
```

### 5. SSL 인증서 발급 (최초 1회)
```bash
# Certbot 컨테이너를 사용하여 SSL 인증서 발급
docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d onair.ai.kr \
  -d www.onair.ai.kr
```

### 6. SSL 인증서 자동 갱신 (선택사항)
```bash
# crontab에 추가하여 자동 갱신 설정
crontab -e

# 매월 1일 자정에 인증서 갱신 시도
0 0 1 * * docker compose run --rm certbot renew && docker compose restart nginx
```

### 7. Nginx 컨테이너 재시작
설정 파일 변경 후:
```bash
docker compose restart nginx
```

## Jenkins CI/CD 설정

### 1. Jenkins Credentials 설정
Jenkins 관리 → Credentials → System → Global credentials에서 다음 항목들을 추가:

#### Database
- `SPRING_DB_USERNAME`: MySQL 사용자명
- `SPRING_DB_PASSWORD`: MySQL 비밀번호

#### Backend
- `JWT_SECRET`: JWT 시크릿 키
- `JWT_ACCESS_TOKEN_EXPIRATION`: Access Token 만료 시간
- `JWT_REFRESH_TOKEN_EXPIRATION`: Refresh Token 만료 시간
- `COMPANY_UUID_EXPIRATION`: Company UUID 만료 시간
- `SPRING_SECURITY_USER_NAME`: Spring Security 사용자명
- `SPRING_SECURITY_USER_PASSWORD`: Spring Security 비밀번호

#### Frontend
- `VITE_API_URL`: API 베이스 URL
- `VITE_SOCKET_URL`: WebSocket URL

#### AI Service
- `JSONL_PATH`: JSONL 데이터 파일 경로
- `FAISS_INDEX_PATH`: FAISS 인덱스 파일 경로
- `EMB_MODEL_NAME`: 임베딩 모델 이름
- `ES_HOST`: Elasticsearch 호스트
- `ES_INDEX`: Elasticsearch 인덱스명
- `CE_MODEL_NAME`: Cross-Encoder 모델 이름
- `GMS_API_KEY`: GMS API 키
- `GCP_TTS_CREDENTIALS_PATH`: GCP TTS 크레덴셜 파일 경로

#### LiveKit
- `LIVEKIT_API_KEY`: LiveKit API 키
- `LIVEKIT_API_SECRET`: LiveKit API 시크릿

### 2. Jenkins Pipeline 설정
1. Jenkins에서 새 Pipeline Job 생성
2. Pipeline script from SCM 선택
3. Git 저장소 URL 및 브랜치 설정
4. Script Path를 `Jenkinsfile`로 설정

### 3. 배포 스크립트
Jenkins는 `scripts/detect-changes.sh`를 사용하여 변경된 서비스를 감지하고, `scripts/deploy.sh`를 통해 선택적 배포를 수행합니다.

## 외부 서비스 설정

### 1. LiveKit 설정
1. [LiveKit Cloud](https://livekit.io/) 가입
2. 프로젝트 생성
3. API Key와 Secret 생성
4. 서버 URL 확인
5. Jenkins Credentials에 등록

### 2. GCP TTS 설정
1. Google Cloud Platform에서 TTS API 활성화
2. 서비스 계정 키 파일 생성
3. EC2 서버에 키 파일 업로드 (예: `/opt/secrets/tts-key.json`)
4. Jenkins Credentials에 경로 등록

### 3. GMS API 설정
1. GMS API 키 발급
2. Jenkins Credentials에 등록

## 배포 확인

### 1. Docker 컨테이너 상태 확인
```bash
# 모든 컨테이너 상태
docker compose ps

# 특정 서비스 로그
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f ai_server
docker compose logs -f vision
docker compose logs -f nginx

# 네트워크 확인
docker network inspect onair-network
```

### 2. Nginx 컨테이너 상태 확인
```bash
# Nginx 컨테이너 상태
docker compose ps nginx

# Nginx 설정 테스트
docker exec nginx nginx -t

# Nginx 로그 확인
docker compose logs -f nginx

# Nginx 컨테이너 내부 접속
docker exec -it nginx /bin/bash
```

### 3. 포트 확인
```bash
# Docker 컨테이너 포트 확인
docker compose ps

# 호스트 포트 확인
netstat -tlnp | grep -E "(80|443|3306|9200|6379)"
```

### 4. API 테스트
```bash
# Backend 헬스체크
curl https://onair.ai.kr/api/actuator/health

# AI Server 헬스체크
curl https://onair.ai.kr/ai/health

# Frontend 접속 확인
curl -I https://onair.ai.kr/
```

### 5. 데이터베이스 연결 확인
```bash
# MySQL 연결 확인
docker exec -it mysql-container mysql -u onair_user -p onair

# Elasticsearch 연결 확인
curl http://localhost:9200

# Redis 연결 확인
docker exec -it redis redis-cli ping
```

### 6. WebSocket 연결 테스트
브라우저 개발자 도구에서 WebSocket 연결 상태를 확인합니다.

## 트러블슈팅

### 1. 컨테이너가 시작되지 않는 경우
```bash
# 로그 확인
docker compose logs [service-name]

# 컨테이너 재시작
docker compose restart [service-name]

# 컨테이너 재빌드
docker compose up -d --build [service-name]
```

### 2. 네트워크 연결 문제
```bash
# 네트워크 확인
docker network inspect onair-network

# 컨테이너를 네트워크에 다시 연결
docker network connect onair-network [container-name]
```

### 3. Nginx 502 Bad Gateway
```bash
# Docker 컨테이너가 실행 중인지 확인
docker compose ps

# Nginx가 Docker 네트워크에 연결되어 있는지 확인
docker network inspect onair-network | grep nginx

# 컨테이너 이름이 올바른지 확인 (spring, react, fastapi)
docker compose ps | grep -E "(spring|react|fastapi)"

# Nginx 설정 파일 확인
docker exec nginx cat /etc/nginx/conf.d/default.conf

# Nginx 에러 로그 확인
docker compose logs nginx | grep error
```

### 4. SSL 인증서 갱신
```bash
# 자동 갱신 테스트
docker compose run --rm certbot renew --dry-run

# 수동 갱신
docker compose run --rm certbot renew
docker compose restart nginx
```
