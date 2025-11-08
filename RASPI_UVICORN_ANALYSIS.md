# 🔍 라즈베리파이 uvicorn 필요 여부 분석

## 📋 현재 구현 상태

### 코드 분석

**`ai_raspi/AI_Supporter/main.py`:**
```python
if __name__ == "__main__":
    t = threading.Thread(target=run_stt_loop, daemon=True)
    t.start()
    uvicorn.run(app, host="0.0.0.0", port=8000)  # ← uvicorn 실행
```

**`ai_raspi/AI_Supporter/server/app.py`:**
```python
app = FastAPI()

@app.post("/api/stt/mode")
async def set_stt_mode(request: SttModeRequest):
    """STT 모드를 변경합니다. Android에서 Intent 분류 후 호출하면 됩니다."""
    # ...

@app.post("/api/stt/intent_done")
async def intent_done(request: IntentDoneRequest):
    """Intent 분류 완료 신호를 받습니다."""
    # ...
```

---

## 🔍 실제 사용 여부 확인

### 모바일에서 라즈베리파이 제어 방법

**현재 구현 (`RaspberryPiControlRepository.kt`):**
```kotlin
// Socket.IO를 통해 제어 명령 전송
socketIoSttClient.sendRaspberryPiControl(
    command = "set_stt_mode",
    data = mapOf("mode" to mode)
)
```

**HTTP POST 사용 여부:** ❌ 없음

모바일 코드를 확인한 결과, 라즈베리파이의 FastAPI 서버(`/api/stt/mode`, `/api/stt/intent_done`)를 직접 호출하는 코드는 **없습니다**.

---

## ✅ 결론

### uvicorn 필요 여부: **선택사항 (현재는 사용 안 함)**

**이유:**
1. **모바일에서 라즈베리파이 제어는 Socket.IO를 통해 이루어짐**
   - `RaspberryPiControlRepository`는 Socket.IO만 사용
   - HTTP POST 엔드포인트는 사용되지 않음

2. **라즈베리파이의 FastAPI 서버는 레거시 코드**
   - `server/app.py`의 엔드포인트들은 정의되어 있지만 실제로 호출되지 않음
   - Socket.IO를 통한 제어로 대체됨

3. **하지만 코드상으로는 uvicorn이 실행됨**
   - `main.py:143`에서 `uvicorn.run(app, ...)` 실행
   - 다만 이 서버는 실제로 사용되지 않음

---

## 🔧 권장 사항

### 옵션 1: uvicorn 제거 (권장)

현재 Socket.IO만 사용하므로 FastAPI 서버는 불필요합니다.

**수정 방법:**
```python
# main.py 수정
if __name__ == "__main__":
    # uvicorn 제거, STT 루프만 실행
    run_stt_loop()
    # 또는
    # threading 없이 직접 실행
    # run_stt_loop()  # 무한 루프이므로 여기서 멈춤
```

**장점:**
- 불필요한 서버 제거
- 리소스 절약
- 코드 단순화

---

### 옵션 2: uvicorn 유지 (선택사항)

향후 HTTP API가 필요할 수 있으므로 유지할 수도 있습니다.

**현재 상태:**
- uvicorn이 실행되지만 실제로는 사용되지 않음
- 포트 8000이 점유됨 (FastAPI 서버와 충돌 가능)

**주의사항:**
- FastAPI 서버(ai_server/rag_server)도 포트 8000 사용
- 라즈베리파이의 FastAPI 서버는 다른 포트 사용 필요

---

## 📊 현재 통신 구조

### 실제 사용되는 통신

```
모바일
  ↓ Socket.IO (control_raspi 이벤트)
FastAPI 서버 (ai_server/rag_server)
  ↓ Socket.IO (control_raspi 이벤트)
라즈베리파이
```

### 사용되지 않는 통신 (레거시)

```
모바일
  ↓ HTTP POST /api/stt/mode
라즈베리파이 FastAPI 서버 (server/app.py)
  ❌ 현재 사용 안 함
```

---

## 🎯 최종 답변

**질문: "uvicorn이 필요하도록 구현되어있어? 아니면 없어도 되게 구현되어있어?"**

**답변:**
- **코드상으로는 uvicorn이 필요하도록 구현되어 있습니다** (`main.py:143`)
- **하지만 실제로는 사용되지 않습니다** (모바일에서 Socket.IO만 사용)
- **따라서 uvicorn 없이도 동작 가능하도록 수정할 수 있습니다**

---

## 🔧 uvicorn 제거 방법

### 방법 1: main.py 수정

```python
# main.py 수정 전
if __name__ == "__main__":
    t = threading.Thread(target=run_stt_loop, daemon=True)
    t.start()
    uvicorn.run(app, host="0.0.0.0", port=8000)

# main.py 수정 후
if __name__ == "__main__":
    # STT 루프만 실행 (무한 루프이므로 여기서 멈춤)
    run_stt_loop()
```

### 방법 2: uvicorn import 제거

```python
# main.py에서 uvicorn import 제거
# import uvicorn  # ← 제거
```

### 방법 3: requirements.txt에서 uvicorn 제거 (선택사항)

```txt
# requirements.txt
# uvicorn[standard]>=0.24.0  # ← 주석 처리 또는 제거
```

---

## ⚠️ 주의사항

1. **포트 충돌 방지**
   - FastAPI 서버(ai_server/rag_server)가 포트 8000 사용
   - 라즈베리파이의 FastAPI 서버도 포트 8000 사용 시 충돌
   - 현재는 uvicorn이 실행되지만 실제로는 사용 안 함

2. **향후 확장성**
   - HTTP API가 필요할 수 있으므로 유지할 수도 있음
   - 하지만 현재는 Socket.IO만 사용

3. **테스트 코드**
   - 일부 테스트 코드에서 라즈베리파이의 FastAPI 서버를 참조할 수 있음
   - 제거 시 테스트 코드도 확인 필요

---

## ✅ 권장 조치

**현재 상황:**
- uvicorn이 실행되지만 실제로는 사용되지 않음
- Socket.IO만 사용

**권장 사항:**
1. **단기:** uvicorn 유지 (코드 변경 최소화)
2. **장기:** uvicorn 제거 (코드 정리 및 리소스 절약)

**즉시 테스트하려면:**
- uvicorn 없이도 동작 가능 (Socket.IO만 사용)
- 하지만 코드상으로는 uvicorn이 실행되므로 포트 충돌 주의

