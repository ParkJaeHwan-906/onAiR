#!/bin/bash

SERVICES="$1"

# 배포할 서비스가 없는 경우 종료
if [ -z "$SERVICES" ]; then
    echo "No services to deploy"
    exit 0
fi

echo "🚀 Deploying: $SERVICES"

# 서비스 빌드 및 실행
docker compose build $SERVICES

# 기존 컨테이너 중지 및 제거
docker compose stop $SERVICES || true
docker compose rm -f $SERVICES || true

# 새 컨테이너 실행
docker compose up -d $SERVICES

# 컨테이너 안정화 대기
sleep 5

# 현재 실행 중인 컨테이너 상태 출력
docker compose ps

echo "✅ Deployment complete: $SERVICES"
