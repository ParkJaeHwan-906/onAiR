#!/bin/bash

CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null)
SERVICES=""

# CI/CD 관련 파일 변경 시 docker compose의 모든 서비스 재배포
if echo "$CHANGED_FILES" | grep -qE "^(Jenkinsfile|docker-compose.yml)"; then
    ALL_SERVICES=$(docker compose config --services 2>/dev/null || echo "")
    if [ -n "$ALL_SERVICES" ]; then
        SERVICES="$ALL_SERVICES"
    else
        # docker-compose config가 실패하면 기본 서비스들
        SERVICES="backend"
    fi
    echo "$SERVICES" | xargs
    exit 0
fi

# backend 변경 감지
if echo "$CHANGED_FILES" | grep -q "^backend/"; then
    SERVICES="$SERVICES backend"
fi

# frontend 변경 감지
if echo "$CHANGED_FILES" | grep -q "^frontend/"; then
    SERVICES="$SERVICES frontend"
fi

# ai_server/rag_server 변경 감지
if echo "$CHANGED_FILES" | grep -q "^ai_server/rag_server/"; then
    SERVICES="$SERVICES ai_server"
fi

# ai_server/yolo_service 변경 감지 (docker-compose.yml의 vision 서비스)
if echo "$CHANGED_FILES" | grep -q "^ai_server/yolo_service/"; then
    SERVICES="$SERVICES vision"
fi

# 변경된 서비스 출력
echo "$SERVICES" | xargs
