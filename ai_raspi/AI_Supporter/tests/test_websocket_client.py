"""
WebSocket 클라이언트 테스트 스크립트
STT 결과를 실시간으로 확인할 수 있습니다.
"""
import asyncio
import websockets
import json

async def test_websocket():
    """WebSocket 연결 테스트"""
    uri = "ws://localhost:8000/ws"
    
    print(f"🔌 WebSocket 연결 시도: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket 연결 성공!")
            print("📡 메시지 수신 대기 중... (종료: Ctrl+C)\n")
            
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=None)
                    data = json.loads(message)
                    
                    msg_type = data.get("type", "unknown")
                    text = data.get("text", "")
                    confidence = data.get("confidence", None)
                    
                    if msg_type == "info":
                        print(f"ℹ️  [{msg_type}] {text}")
                    elif msg_type == "final":
                        conf_str = f" (신뢰도: {confidence:.2f})" if confidence else ""
                        print(f"📝 [{msg_type}] {text}{conf_str}")
                    elif msg_type == "interim":
                        print(f"🔄 [{msg_type}] {text}")
                    elif msg_type == "error":
                        print(f"❌ [{msg_type}] {text}")
                    else:
                        print(f"📨 [{msg_type}] {data}")
                        
                except websockets.exceptions.ConnectionClosed:
                    print("\n🔌 WebSocket 연결 종료")
                    break
                except Exception as e:
                    print(f"❌ 오류: {e}")
                    break
                    
    except ConnectionRefusedError:
        print("❌ 연결 실패: 서버가 실행 중이지 않습니다.")
        print("   먼저 'python main.py'를 실행하세요.")
    except Exception as e:
        print(f"❌ 오류: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_websocket())
    except KeyboardInterrupt:
        print("\n👋 종료")

