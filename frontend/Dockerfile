# =============== Build Stage ===============

# Node.js 18버전의 Alpine Linux 기반 이미지 사용 
# Alpine은 경량화된 리눅스 배포판 
# AS builder : 해당 스테이지를 'builder'라고 지정 
FROM node:22-alpine AS builder

# 컨테이너 내부에서 /app 디렉토리를 작업 디렉토리로 설정
# 이후 모든 명령어가 해당 디렉토리에서 실행 
WORKDIR /app

# Vite 환경변수를 빌드 타임에 주입하기 위한 ARG 선언
ARG VITE_API_URL
ARG VITE_SOCKET_URL

# ARG를 ENV로 변환 (Vite가 빌드 시 접근 가능하도록)
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_SOCKET_URL=${VITE_SOCKET_URL}

# package.json과 package-lock.json 파일을 컨테이너의 /app 디렉토리로 복사 
# 소스 코드보다 먼저 복사 -> Docker 레이어 캐싱 최적화 (?)
COPY package*.json ./

# npm ci : package-lock.json을 기반으로 정확한 버전의 의존성 설치 
# 빌드 스테이지에서는 devDependencies도 필요 (typescript, vite 등)
# npm cache clean --force : npm 캐시 삭제로 이미지 크기 감소 
# RUN npm ci && npm cache clean --force
RUN rm -rf node_modules package-lock.json \
    && npm install \
    && npm cache clean --force

# 현재 디렉토리의 모든 소스코드를 컨테이너의 /app 디렉토리로 복사 
COPY . .

# React 프로젝트를 프로덕션 빌드 
RUN npm run build

# =============== Runtime Stage ===============

# 빌드 스테이지와 같은 베이스 이미지 사용 
FROM node:22-alpine

# 컨테이너 내부의 작업 디렉토리를 /app으로 설정 
WORKDIR /app

# serve 패키지 전역 설치 (경량 정적 파일 서버)
RUN npm install -g serve

# 빌드된 파일만 복사
# Vite는 build 폴더 말고 dist 폴더에 빌드됨! 
COPY --from=builder /app/dist ./dist

# 포트 노출 (기본적으로 serve는 3000 포트 사용)
EXPOSE 3000

# serve로 빌드된 파일 제공
# serve는 기본적으로 localhost에만 바인딩되어 다른 컨테이너에서 접근 불가
# 0.0.0.0으로 바인딩하여 같은 Docker 네트워크 내의 Nginx 컨테이너에서 접근 가능하도록 설정
CMD ["serve", "-s", "dist", "-l", "tcp://0.0.0.0:3000"]