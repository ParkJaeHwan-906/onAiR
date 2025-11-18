# 전체 로직 플로우 가이드

## 📋 목차

1. [Wakeword 감지부터 시작하는 전체 플로우](#1-wakeword-감지부터-시작하는-전체-플로우)
2. [케이스별 상세 로직](#2-케이스별-상세-로직)
3. [메인루프 종료 시점](#3-메인루프-종료-시점)
4. [종료 후 상태 복귀](#4-종료-후-상태-복귀)
5. [예외 처리](#5-예외-처리)

---

## 1. Wakeword 감지부터 시작하는 전체 플로우

### 🔄 메인 루프 구조 (라즈베리파이)

```
┌─────────────────────────────────────────────────────────┐
│ ① Wakeword 감지 대기 상태 (초기 상태)                    │
│    - 마이크: ON                                          │
│    - Wakeword 감지기: 활성화                             │
│    - 서비스 진행 중 플래그: False                        │
└─────────────────────────────────────────────────────────┘
                    ↓ (Wakeword 감지)
┌─────────────────────────────────────────────────────────┐
│ ② Wakeword 감지 성공                                     │
│    - Wakeword 감지기: 일시 중지                          │
│    - 서비스 진행 중 플래그: True                          │
│    - FastAPI로 wakeword_detected 이벤트 전송              │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ ③ 버퍼링 STT 세션 시작                                   │
│    - 마이크: ON (STT 목적)                               │
│    - 버퍼링 STT 실행 (약 3초)                            │
│    - STT 결과를 FastAPI로 전송                           │
│    - 마이크: OFF (STT 목적)                              │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ ④ Intent 분류 대기                                       │
│    - FastAPI에서 Intent 분류 수행                        │
│    - 모바일로 Intent 결과 전송                           │
│    - 모바일에서 Intent 음성 파일 재생                    │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ ⑤ Intent별 분기 처리                                     │
│    ├─ AI_SUPPORTER → CV 탐지 로직                        │
│    ├─ OPERATOR → WebRTC 통신 대기                        │
│    └─ 기타 → Streaming STT 세션 시작                    │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ ⑥ 서비스 완료 대기                                       │
│    - service_completed 이벤트 대기                       │
│    - 또는 wakeword_start_waiting 이벤트 수신             │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ ⑦ Wakeword 감지 대기 상태로 복귀                        │
│    - 마이크: ON                                          │
│    - Wakeword 감지기: 활성화                             │
│    - 서비스 진행 중 플래그: False                        │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 케이스별 상세 로직

### 📌 케이스 1: AI_SUPPORTER (CV 탐지 성공)

#### 전체 플로우

```
① Wakeword 감지
   ↓
② 버퍼링 STT 실행
   ↓
③ Intent 분류 → AI_SUPPORTER
   ↓
④ CV 모델 실행
   ↓
⑤ CV 탐지 성공 확인
   ↓
⑥ [1단계] 간단한 알림 생성 및 전송
   - GPT-4o로 알림 메시지 생성
   - TTS 변환
   - 모바일로 cv_detection_anomaly 이벤트 전송
   ↓
⑦ 모바일: 알림 TTS 재생 → 모달 표시 ("답변 생성 중...")
   ↓
⑧ 모바일: audio_playback_completed (type="cv_detection_anomaly") 전송
   ↓
⑨ [2단계] 전체 정비 가이드 생성 및 전송
   - RAG 검색
   - GPT-4o로 정비 가이드 생성
   - 각 섹션별 TTS 변환
   - 모바일로 final_answer 이벤트 전송
   ↓
⑩ 모바일: 모달 숨김
   ↓
⑪ 모바일: 각 섹션별 마크다운 표시 + 오디오 재생
   - possible_causes (원인)
   - 2초 대기
   - recommended_actions (조치)
   - 2초 대기
   - safety_warnings (주의사항)
   ↓
⑫ 모바일: 마지막 섹션 완료 → audio_playback_completed (type="final_answer") 전송
   ↓
⑬ FastAPI: wakeword_start_waiting 이벤트 전송
   ↓
⑭ 라즈베리파이: Wakeword 감지 대기 상태로 복귀
```

#### 메인루프 종료 시점

- **라즈베리파이 메인루프**: `wakeword_start_waiting` 이벤트 수신 시 종료
- **FastAPI 로직**: `audio_playback_completed` (type="final_answer") 수신 시 종료
- **모바일 로직**: 마지막 섹션(safety_warnings) 오디오 재생 완료 시 종료

#### 종료 후 상태 복귀

- **라즈베리파이**:
  - `service_in_progress["in_progress"] = False`
  - 마이크: ON
  - Wakeword 감지기: 활성화
  - `reset_to_wakeword_waiting("서비스 완료", allow_new_service=True)`

- **FastAPI**:
  - `_pending_cv_detection = None` (전역 변수 초기화)
  - 세션 정보 유지 (다음 wakeword 감지 대기)

- **모바일**:
  - 모달 숨김
  - 세션 정보 초기화 (`sessionManager.resetSession()`)

---

### 📌 케이스 2: AI_SUPPORTER (CV 탐지 실패)

#### 전체 플로우

```
① Wakeword 감지
   ↓
② 버퍼링 STT 실행
   ↓
③ Intent 분류 → AI_SUPPORTER
   ↓
④ CV 모델 실행
   ↓
⑤ CV 탐지 실패 확인
   ↓
⑥ 모바일로 cv_detection_failed 이벤트 전송
   ↓
⑦ 라즈베리파이로 cv_detection_failed 이벤트 전송
   ↓
⑧ 모바일: cv_detection_failed 음성 파일 재생
   ↓
⑨ 모바일: audio_playback_completed (type="cv_detection_failed") 전송
   ↓
⑩ WebRTC 오디오 스트리밍 대기 상태 (OPERATOR와 동일)
   ↓
⑪ accept_communication 이벤트 수신 시 WebRTC 통신 시작
   ↓
⑫ 통신 종료 → 마이크 재점유
   ↓
⑬ 라즈베리파이: Wakeword 감지 대기 상태로 복귀
```

**참고**: Streaming STT → Clarify 루프 로직은 주석처리되어 있으며, 현재는 OPERATOR와 동일하게 WebRTC 통신 연결로 처리됩니다.

#### 메인루프 종료 시점

- **라즈베리파이 메인루프**: `mic_acquire` 콜백 호출 시 종료 (통신 종료 후)
- **FastAPI 로직**: WebRTC 통신 종료 시 종료
- **모바일 로직**: 통신 종료 시 종료

#### 종료 후 상태 복귀

- **라즈베리파이**:
  - `service_in_progress["in_progress"] = False`
  - 마이크: ON (재점유)
  - Wakeword 감지기: 활성화
  - `service_completed_flag_global["completed"] = True`

- **FastAPI**:
  - WebRTC 세션 종료

- **모바일**:
  - WebRTC 통신 종료

---

### 📌 케이스 3: AI_SUPPORTER (CV 탐지 정상)

#### 전체 플로우

```
① Wakeword 감지
   ↓
② 버퍼링 STT 실행
   ↓
③ Intent 분류 → AI_SUPPORTER
   ↓
④ CV 모델 실행
   ↓
⑤ CV 탐지 정상 확인
   ↓
⑥ 모바일로 cv_detection_normal 이벤트 전송
   ↓
⑦ 라즈베리파이로 cv_detection_success 이벤트 전송
   ↓
⑧ 모바일: cv_detection_normal 음성 파일 재생
   ↓
⑨ 모바일: audio_playback_completed (type="cv_detection_normal") 전송
   ↓
⑩ WebRTC 오디오 스트리밍 대기 상태 (OPERATOR와 동일)
   ↓
⑪ accept_communication 이벤트 수신 시 WebRTC 통신 시작
   ↓
⑫ 통신 종료 → 마이크 재점유
   ↓
⑬ 라즈베리파이: Wakeword 감지 대기 상태로 복귀
```

#### 메인루프 종료 시점

- **라즈베리파이 메인루프**: `mic_acquire` 콜백 호출 시 종료 (통신 종료 후)
- **FastAPI 로직**: WebRTC 통신 종료 시 종료
- **모바일 로직**: 통신 종료 시 종료

#### 종료 후 상태 복귀

- **라즈베리파이**:
  - `service_in_progress["in_progress"] = False`
  - 마이크: ON (재점유)
  - Wakeword 감지기: 활성화
  - `service_completed_flag_global["completed"] = True`

- **FastAPI**:
  - WebRTC 세션 종료

- **모바일**:
  - WebRTC 통신 종료

---

### 📌 케이스 4: OPERATOR

#### 전체 플로우

```
① Wakeword 감지
   ↓
② 버퍼링 STT 실행
   ↓
③ Intent 분류 → OPERATOR
   ↓
④ 모바일로 Intent 결과 전송
   ↓
⑤ 모바일: OPERATOR 음성 파일 재생
   ↓
⑥ 모바일: audio_playback_completed (type="intent") 전송
   ↓
⑦ WebRTC 오디오 스트리밍 대기 상태
   ↓
⑧ accept_communication 이벤트 수신 시 WebRTC 통신 시작
   ↓
⑨ 통신 종료 → 마이크 재점유
   ↓
⑩ 라즈베리파이: Wakeword 감지 대기 상태로 복귀
```

#### 메인루프 종료 시점

- **라즈베리파이 메인루프**: `mic_acquire` 콜백 호출 시 종료 (통신 종료 후)
- **FastAPI 로직**: WebRTC 통신 종료 시 종료
- **모바일 로직**: 통신 종료 시 종료

#### 종료 후 상태 복귀

- **라즈베리파이**:
  - `service_in_progress["in_progress"] = False`
  - 마이크: ON (재점유)
  - Wakeword 감지기: 활성화
  - `service_completed_flag_global["completed"] = True`

- **FastAPI**:
  - WebRTC 세션 종료

- **모바일**:
  - WebRTC 통신 종료

---

### 📌 케이스 5: 일반 질문 (Streaming STT + Clarify 루프)

**참고**: 현재 이 케이스는 사용되지 않습니다. CV 탐지 실패 시에도 OPERATOR와 동일하게 WebRTC 통신 연결로 처리됩니다.

#### 전체 플로우 (주석처리된 로직)

```
① Wakeword 감지
   ↓
② 버퍼링 STT 실행
   ↓
③ Intent 분류 → 기타
   ↓
④ 라즈베리파이: Streaming STT 세션 시작
   ↓
⑤ Streaming STT 실행 (사용자 질문 수집)
   ↓
⑥ FastAPI: RAG 검색 + Evidence Check
   ↓
⑦ Evidence Check 결과:
   ├─ RED/YELLOW → Clarify 질문 생성 및 전송
   │   ↓
   │   ⑧ 모바일: Clarify 질문 TTS 재생
   │   ↓
   │   ⑨ 모바일: audio_playback_completed (type="clarify_qa_turn") 전송
   │   ↓
   │   ⑩ 다음 Streaming STT 질문 대기 (⑤로 복귀)
   │
   └─ GREEN → 최종 답변 생성
       ↓
       ⑧ FastAPI: GPT-4o로 최종 답변 생성
       ↓
       ⑨ FastAPI: Streaming STT 세션 종료
       ↓
       ⑩ 모바일로 final_answer 이벤트 전송
       ↓
       ⑪ 모바일: 최종 답변 TTS 재생
       ↓
       ⑫ 모바일: audio_playback_completed (type="final_answer") 전송
       ↓
       ⑬ FastAPI: wakeword_start_waiting 이벤트 전송
       ↓
       ⑭ 라즈베리파이: Wakeword 감지 대기 상태로 복귀
```

#### 메인루프 종료 시점

- **라즈베리파이 메인루프**: `wakeword_start_waiting` 이벤트 수신 시 종료
- **FastAPI 로직**: `audio_playback_completed` (type="final_answer") 수신 시 종료
- **모바일 로직**: 최종 답변 TTS 재생 완료 시 종료

#### 종료 후 상태 복귀

- **라즈베리파이**:
  - `service_in_progress["in_progress"] = False`
  - 마이크: ON
  - Wakeword 감지기: 활성화
  - `reset_to_wakeword_waiting("서비스 완료", allow_new_service=True)`

- **FastAPI**:
  - 세션 정보 초기화 (`memory.clear_history(session_id)`)
  - `clarify_sessions.pop(session_id, None)`

- **모바일**:
  - 세션 정보 초기화 (`sessionManager.resetSession()`)

---

## 3. 메인루프 종료 시점

### 🔴 라즈베리파이 메인루프 종료 시점

#### 정상 종료 시점

1. **CV 탐지 성공 케이스**:
   - `wakeword_start_waiting` 이벤트 수신 시
   - `service_completed_flag_global["completed"] = True` 확인 후 종료

2. **CV 탐지 실패/정상 케이스**:
   - `wakeword_start_waiting` 이벤트 수신 시
   - 또는 `mic_acquire` 콜백 호출 시 (WebRTC 통신 종료 후)

3. **일반 질문 케이스**:
   - `wakeword_start_waiting` 이벤트 수신 시
   - `service_completed_flag_global["completed"] = True` 확인 후 종료

#### 메인루프 구조

```python
while True:
    try:
        # ① Wakeword 감지 대기
        wakeword_detected = wait_for_wakeword(timeout=1.0)
        
        if wakeword_detected:
            # ② Wakeword 감지 성공
            service_in_progress["in_progress"] = True
            
            # ③ 버퍼링 STT 실행
            # ④ Intent 분류 대기
            # ⑤ Intent별 분기 처리
            
            # ⑥ 서비스 완료 대기
            service_completed_flag_global["completed"] = False
            while not service_completed_flag_global["completed"]:
                # 타임아웃 체크 (60초)
                # service_completed 이벤트 대기
                # 또는 wakeword_start_waiting 이벤트 수신
            
            # ⑦ Wakeword 감지 대기 상태로 복귀
            reset_to_wakeword_waiting("서비스 완료", allow_new_service=True)
    except Exception as e:
        # 예외 처리
        reset_to_wakeword_waiting(f"오류: {e}", allow_new_service=False)
```

---

### 🔴 FastAPI 로직 종료 시점

#### 정상 종료 시점

1. **CV 탐지 성공 케이스**:
   - `audio_playback_completed` (type="final_answer") 수신 시
   - `wakeword_start_waiting` 이벤트 전송 후 종료

2. **CV 탐지 실패 케이스**:
   - `audio_playback_completed` (type="final_answer") 수신 시
   - `wakeword_start_waiting` 이벤트 전송 후 종료

3. **일반 질문 케이스**:
   - `audio_playback_completed` (type="final_answer") 수신 시
   - `wakeword_start_waiting` 이벤트 전송 후 종료

#### FastAPI 로직 구조

```python
# CV 탐지 성공 케이스
async def handle_audio_playback_completed(sid, data):
    if audio_type == "cv_detection_anomaly":
        # [2단계] 전체 정비 가이드 생성 및 전송
        # ...
        await broadcast_to("mobile", "final_answer", {...})
    
    elif audio_type == "final_answer":
        # 서비스 로직 종료
        await broadcast_to("raspi", "wakeword_start_waiting", {})
        # 로직 종료
```

---

### 🔴 모바일 로직 종료 시점

#### 정상 종료 시점

1. **CV 탐지 성공 케이스**:
   - 마지막 섹션(safety_warnings) 오디오 재생 완료 시
   - `sendFinalAnswerAudioCompleted()` 호출 후 종료

2. **CV 탐지 실패 케이스**:
   - 최종 답변 TTS 재생 완료 시
   - `sendFinalAnswerAudioCompleted()` 호출 후 종료

3. **일반 질문 케이스**:
   - 최종 답변 TTS 재생 완료 시
   - `sendFinalAnswerAudioCompleted()` 호출 후 종료

#### 모바일 로직 구조

```kotlin
// CV 탐지 성공 케이스
private fun handleStructuredAnswerSections(structuredAnswer: Map<String, Any>) {
    lifecycleScope.launch {
        // 각 섹션별 처리
        processSection("원인", ...) {
            delay(2000)
            processSection("조치", ...) {
                delay(2000)
                processSection("주의사항", ...) {
                    // 마지막 섹션 완료
                    socketIoSttClient.sendFinalAnswerAudioCompleted()
                }
            }
        }
    }
}
```

---

## 4. 종료 후 상태 복귀

### 🔄 라즈베리파이 상태 복귀

#### `reset_to_wakeword_waiting()` 함수

```python
def reset_to_wakeword_waiting(reason: str = "알 수 없는 오류", allow_new_service: bool = True):
    """
    Wakeword 감지 대기 상태로 복귀
    
    Args:
        reason: 복귀 이유
        allow_new_service: 새로운 서비스 시작 허용 여부
                          - True: 정상 완료 시 즉시 플래그 해제
                          - False: 예외 발생 시 2초 대기 후 플래그 해제
    """
    # 1. 서비스 진행 중 플래그 해제
    if allow_new_service:
        service_in_progress["in_progress"] = False
    else:
        # 2초 대기 후 플래그 해제 (별도 스레드)
        delayed_flag_reset()
    
    # 2. 마이크 활성화
    if not mic.is_active():
        mic.resume()
    
    # 3. Wakeword 감지기 재개
    if allow_new_service:
        wakeword_detector.resume()
        mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)
    
    # 4. 버퍼링 STT 실행 상태 리셋
    buffered_stt_running["running"] = False
    
    # 5. FastAPI로 Wakeword 대기 준비 완료 이벤트 전송
    if allow_new_service:
        send_wakeword_waiting_ready()
```

#### 상태 복귀 시점별 동작

| 케이스 | `allow_new_service` | 즉시 플래그 해제 | Wakeword 감지기 재개 |
|--------|---------------------|------------------|---------------------|
| 정상 완료 | `True` | ✅ 즉시 | ✅ 즉시 |
| 예외 발생 | `False` | ⏱️ 2초 후 | ⏱️ 2초 후 |

---

### 🔄 FastAPI 상태 복귀

#### 세션 정보 초기화

```python
# Clarify 루프 완료 시
memory.clear_history(session_id)
clarify_sessions.pop(session_id, None)

# CV 탐지 성공 시
_pending_cv_detection = None
```

#### 상태 복귀 시점별 동작

| 케이스 | 세션 정보 초기화 | 전역 변수 초기화 |
|--------|------------------|-----------------|
| CV 탐지 성공 | ❌ (세션 없음) | ✅ `_pending_cv_detection = None` |
| CV 탐지 실패 | ✅ `memory.clear_history()` | ❌ |
| 일반 질문 | ✅ `memory.clear_history()` | ❌ |

---

### 🔄 모바일 상태 복귀

#### 세션 정보 초기화

```kotlin
// 최종 답변 수신 시
isWaitingForClarification = false
sessionManager.resetSession()
currentSessionId = null
currentTurnId = 1
```

#### 상태 복귀 시점별 동작

| 케이스 | 세션 정보 초기화 | 모달 숨김 |
|--------|------------------|----------|
| CV 탐지 성공 | ✅ `sessionManager.resetSession()` | ✅ `hideModal()` |
| CV 탐지 실패 | ✅ `sessionManager.resetSession()` | ❌ |
| 일반 질문 | ✅ `sessionManager.resetSession()` | ❌ |

---

## 5. 예외 처리

### 🔴 라즈베리파이 예외 처리

#### 예외 처리 구조

```python
try:
    # 메인 루프 실행
    while True:
        try:
            # Wakeword 감지
            # 버퍼링 STT 실행
            # 서비스 완료 대기
        except Exception as e:
            # 메인 루프 실행 오류
            reset_to_wakeword_waiting(f"메인 루프 실행 오류: {e}", allow_new_service=False)
            continue
        except BaseException as e:
            # 시스템 예외
            if isinstance(e, KeyboardInterrupt):
                raise
            reset_to_wakeword_waiting(f"메인 루프 시스템 오류: {e}", allow_new_service=False)
            continue
except KeyboardInterrupt:
    # 종료 처리
    streaming_stt.stop()
    mic.stop()
    stop_wakeword_detector()
except Exception as e:
    # 최상위 예외
    reset_to_wakeword_waiting(f"최상위 예외: {e}", allow_new_service=False)
    raise
```

#### 예외 처리 시점별 동작

| 예외 발생 시점 | `allow_new_service` | 처리 방법 |
|---------------|---------------------|----------|
| Wakeword 감지 오류 | `False` | 2초 대기 후 플래그 해제 |
| STT 세션 실행 오류 | `False` | 2초 대기 후 플래그 해제 |
| 서비스 완료 대기 타임아웃 | `False` | 2초 대기 후 플래그 해제 |
| 메인 루프 실행 오류 | `False` | 2초 대기 후 플래그 해제 |
| 최상위 예외 | `False` | 2초 대기 후 플래그 해제, 프로그램 종료 |

---

### 🔴 FastAPI 예외 처리

#### 예외 처리 구조

```python
# CV 모델 실행 오류
try:
    cv_raw = await run_anomaly_detection()
except Exception as e:
    # CV 모델 오류 시 탐지 실패로 처리
    await broadcast_to("mobile", "cv_detection_failed", {...})
    await broadcast_to("raspi", "cv_detection_failed", {...})

# RAG 검색 또는 답변 생성 실패
try:
    # RAG 검색
    # GPT-4o 답변 생성
except Exception as e:
    # 빈 structured_answer 전송
    structured_answer = {
        "error_code": query,
        "markdown_text": "",
        "possible_causes": [],
        "recommended_actions": [],
        "safety_warnings": [],
        # ... (모든 필드 포함)
    }
```

#### 예외 처리 시점별 동작

| 예외 발생 시점 | 처리 방법 |
|---------------|----------|
| CV 모델 실행 오류 | `cv_detection_failed` 이벤트 전송 |
| RAG 검색 실패 | 빈 `structured_answer` 전송 |
| GPT-4o 호출 실패 | 빈 `structured_answer` 전송 (마크다운 필드 포함) |
| TTS 변환 실패 | 오디오는 `None`, 로직은 계속 진행 |

---

### 🔴 모바일 예외 처리

#### 예외 처리 구조

```kotlin
// CV 탐지 이상 처리
try {
    // TTS 재생
    // 모달 표시
    // 이벤트 전송
} catch (e: Exception) {
    Log.e(TAG, "❌ CV 탐지 이상 처리 오류: ${e.message}")
    e.printStackTrace()
}

// 섹션별 처리
try {
    // 각 섹션별 처리
} catch (e: Exception) {
    Log.e(TAG, "❌ 섹션별 처리 오류: ${e.message}")
    e.printStackTrace()
    // 오류 발생 시에도 서비스 종료 처리
    socketIoSttClient.sendFinalAnswerAudioCompleted()
}
```

#### 예외 처리 시점별 동작

| 예외 발생 시점 | 처리 방법 |
|---------------|----------|
| TTS 재생 실패 | 로그 출력, 다음 단계 진행 |
| 모달 표시 실패 | 로그 출력, 다음 단계 진행 |
| 이벤트 전송 실패 | 로그 출력, 다음 단계 진행 |
| 섹션별 처리 오류 | 로그 출력, 서비스 종료 처리 |

---

## 📊 전체 상태 머신 다이어그램

```
┌─────────────────────────────────────────────────────────┐
│                    초기 상태                             │
│  - 마이크: ON                                            │
│  - Wakeword 감지기: 활성화                               │
│  - 서비스 진행 중 플래그: False                          │
└─────────────────────────────────────────────────────────┘
                    ↓ (Wakeword 감지)
┌─────────────────────────────────────────────────────────┐
│              서비스 진행 중 상태                          │
│  - 마이크: ON/OFF (상황에 따라)                          │
│  - Wakeword 감지기: 일시 중지                            │
│  - 서비스 진행 중 플래그: True                           │
└─────────────────────────────────────────────────────────┘
                    ↓ (서비스 완료)
┌─────────────────────────────────────────────────────────┐
│         Wakeword 감지 대기 상태로 복귀                    │
│  - 마이크: ON                                            │
│  - Wakeword 감지기: 활성화                               │
│  - 서비스 진행 중 플래그: False                          │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 핵심 포인트

### 1. 메인루프 종료 조건

- **라즈베리파이**: `service_completed_flag_global["completed"] = True` 또는 `wakeword_start_waiting` 이벤트 수신
- **FastAPI**: `audio_playback_completed` (type="final_answer") 수신
- **모바일**: 마지막 섹션 오디오 재생 완료 또는 최종 답변 TTS 재생 완료

### 2. 상태 복귀 메커니즘

- **정상 완료**: `allow_new_service=True` → 즉시 플래그 해제 및 Wakeword 감지기 재개
- **예외 발생**: `allow_new_service=False` → 2초 대기 후 플래그 해제 (서비스 겹침 방지)

### 3. 예외 처리 원칙

- **모든 예외는 로그 출력 후 다음 단계 진행**
- **예외 발생 시에도 서비스 종료 처리 보장**
- **빈 데이터 구조라도 필드 구조는 유지**

---

## 📝 참고 사항

1. **서비스 겹침 방지**: 예외 발생 시 `allow_new_service=False`로 설정하여 2초 대기 후 플래그 해제
2. **타임아웃 처리**: 서비스 완료 대기 시 60초 타임아웃 설정
3. **세션 관리**: 각 케이스별로 세션 정보 초기화 시점이 다름
4. **마이크 상태 관리**: 상황에 따라 마이크 ON/OFF 상태가 변경됨

