#!/bin/bash
# ======================================
# 라즈베리 내부 브리지 자동 실행 스크립트 (venv 미사용 버전)
# ======================================

echo "🚀 Python 3.10 STT 브리지 서버 실행 중..."
python3.10 /home/pi/AI_Supporter/bridge/stt_bridge_server.py &

sleep 2  # 서버 안정화 대기

echo "⚡ Python 3.13 브리지 클라이언트 실행 중..."
python3.13 /home/pi/AI_Supporter/bridge/stt_bridge_client.py &

echo "✅ 모든 프로세스가 실행되었습니다."
