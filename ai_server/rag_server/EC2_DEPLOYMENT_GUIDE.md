# EC2 FastAPI 서버 배포 가이드

## 현재 상황

- **Spring 서버**: `https://onair.ai.kr/api` (도메인 사용)
- **FastAPI 서버**: 도메인 없음, EC2에 배포됨

## FastAPI 서버 URL 설정 옵션

### 옵션 1: EC2 공인 IP 사용 (가장 간단)

**장점:**
- 추가 설정 불필요
- 즉시 사용 가능

**단점:**
- IP 주소가 변경될 수 있음 (Elastic IP 사용 권장)
- HTTP만 사용 (HTTPS 설정 필요 시 추가 작업)

**설정 방법:**

1. EC2 인스턴스의 공인 IP 확인:
   ```bash
   # EC2 콘솔에서 확인하거나
   curl http://169.254.169.254/latest/meta-data/public-ipv4
   ```

2. 모바일 앱 설정 (`MainActivitySttServer.kt`):
   ```kotlin
   private val FASTAPI_SERVER_URL = "http://13.125.xxx.xxx:8000"  // EC2 공인 IP
   ```

3. FastAPI 서버 설정 (`app/core/config.py`):
   ```python
   FASTAPI_SERVER_URL: str = "http://13.125.xxx.xxx:8000"
   ```

**보안 그룹 설정:**
- EC2 보안 그룹에서 포트 8000 인바운드 규칙 추가 필요

---

### 옵션 2: 서브도메인 사용 (권장)

**장점:**
- 도메인 기반으로 안정적
- HTTPS 설정 가능
- IP 변경에 영향 없음

**단점:**
- DNS 설정 필요
- SSL 인증서 설정 필요 (Let's Encrypt 사용 가능)

**설정 방법:**

1. DNS 설정 (Route 53 또는 도메인 제공자):
   ```
   api.onair.ai.kr → EC2 공인 IP
   ```

2. Nginx 리버스 프록시 설정 (EC2에 설치):
   ```nginx
   server {
       listen 80;
       server_name api.onair.ai.kr;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

3. 모바일 앱 설정:
   ```kotlin
   private val FASTAPI_SERVER_URL = "http://api.onair.ai.kr"  // 또는 https://api.onair.ai.kr
   ```

4. FastAPI 서버 설정:
   ```python
   FASTAPI_SERVER_URL: str = "http://api.onair.ai.kr"  # 또는 https
   ```

---

### 옵션 3: 같은 도메인에 경로로 설정

**장점:**
- 하나의 도메인으로 통합
- SSL 인증서 재사용 가능

**단점:**
- Nginx 리버스 프록시 설정 필요
- Spring 서버와 같은 포트 사용

**설정 방법:**

1. Nginx 설정 (Spring 서버와 같은 서버 또는 별도 서버):
   ```nginx
   server {
       listen 443 ssl;
       server_name onair.ai.kr;
       
       # Spring 서버
       location /api {
           proxy_pass http://spring-server:8080;
       }
       
       # FastAPI 서버
       location /fastapi {
           proxy_pass http://localhost:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

2. 모바일 앱 설정:
   ```kotlin
   private val FASTAPI_SERVER_URL = "https://onair.ai.kr/fastapi"
   ```

3. FastAPI 서버 설정:
   ```python
   FASTAPI_SERVER_URL: str = "https://onair.ai.kr/fastapi"
   ```

**주의사항:**
- Socket.IO 경로가 `/ws`이므로, 실제 경로는 `https://onair.ai.kr/fastapi/ws`가 됩니다.
- FastAPI 서버의 Socket.IO 경로 설정 확인 필요

---

## 권장 사항

### 단기 (테스트용)
**옵션 1: EC2 공인 IP 사용**
- Elastic IP 할당하여 IP 고정
- 모바일 앱에 IP 주소 하드코딩

### 장기 (프로덕션)
**옵션 2: 서브도메인 사용**
- `api.onair.ai.kr` 서브도메인 생성
- Nginx 리버스 프록시 설정
- Let's Encrypt로 SSL 인증서 발급
- HTTPS 사용

---

## EC2 보안 그룹 설정

FastAPI 서버에 접근하려면 EC2 보안 그룹에서 다음 규칙 추가:

```
인바운드 규칙:
- Type: Custom TCP
- Port: 8000
- Source: 0.0.0.0/0 (또는 특정 IP만 허용)
```

---

## 확인 방법

1. EC2에서 서버 실행:
   ```bash
   uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000
   ```

2. 브라우저에서 접속 테스트:
   - `http://EC2_공인_IP:8000`
   - `http://EC2_공인_IP:8000/docs` (Swagger UI)

3. 모바일 앱에서 Socket.IO 연결 테스트:
   - 로그에서 "✅ Socket.IO 서버 연결 성공" 확인

