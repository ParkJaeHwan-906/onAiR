#!/bin/bash
# 마이크 사용 중인 프로세스 확인 스크립트

echo "🔍 마이크 사용 중인 프로세스 확인"
echo "=================================="

echo ""
echo "1. /dev/snd 디바이스 사용 중인 프로세스:"
echo "----------------------------------------"
lsof /dev/snd/* 2>/dev/null | grep -v "COMMAND" || echo "  사용 중인 프로세스 없음"

echo ""
echo "2. Python 프로세스 확인:"
echo "----------------------------------------"
ps aux | grep python | grep -v grep

echo ""
echo "3. WebRTC 오디오 스트리밍 프로세스 확인:"
echo "----------------------------------------"
ps aux | grep -E "socket_manager|AudioService|stream_audio" | grep -v grep || echo "  실행 중이지 않음"

echo ""
echo "4. 포트 5050 사용 중인 프로세스:"
echo "----------------------------------------"
lsof -i :5050 2>/dev/null || echo "  포트 5050 사용 중인 프로세스 없음"

echo ""
echo "💡 WebRTC 오디오 스트리밍이 실행 중이면 마이크를 점유할 수 있습니다."
echo "   Python 3.13 프로세스를 확인하세요: ps aux | grep python3.13"

