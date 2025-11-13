# 🎯 전체 시스템 흐름 및 소켓 이벤트 정리

## 📌 중요 사항
- **마이크는 하나**이며, 시점별로 음성을 어디에 활용하는지만 다릅니다.
- **STT 목적**: GCP STT로 전송하거나 Wakeword 감지에 사용
- **WebRTC 오디오 스트리밍 목적**: Socket.IO `audio_frame` 이벤트로 전송

---

## 🔄 케이스별 상세 흐름

### 📍 케이스 1: 초기 상태 → Wakeword 감지 → 버퍼링 STT → Intent 분류

#### 1-1. 초기 상태
```
[라즈베리파이]
├─ 마이크 상태: STT 목적 음성 수집 ON (MicStream.start())
├─ Wakeword 감지: 활성화 (wakeword_detector.resume())
└─ 상태: Wakeword 감지 대기 중
```

#### 1-2. Wakeword 감지
```
[라즈베리파이 Python 3.10]
├─ Wakeword 감지 완료
├─ Wakeword 콜백 비활성화 (mic.disable_wakeword_callback())
├─ Wakeword 감지기 일시 중지 (wakeword_detector.pause())
└─ 소켓 이벤트 전송:
    └─ 브리지 서버 → 브리지 클라이언트 → FastAPI
       이벤트: wakeword_detected
       데이터: {}

[FastAPI]
├─ 이벤트 수신: wakeword_detected (라즈베리파이로부터)
└─ 소켓 이벤트 전송:
    └─ 모바일로
       이벤트: wakeword_detected
       데이터: {"timestamp": null}

[모바일]
├─ 이벤트 수신: wakeword_detected
├─ 음성 파일 재생: "onAir 서비스를 시작합니다. 어떤 것을 도와드릴까요?"
└─ 재생 완료 후 소켓 이벤트 전송:
    └─ FastAPI로
       이벤트: wakeword_audio_completed
       데이터: {"timestamp": ...}

[FastAPI]
├─ 이벤트 수신: wakeword_audio_completed
└─ 버퍼링 STT 시작 신호 전송 (이미 라즈베리파이에서 자동 시작됨)
```

#### 1-3. 버퍼링 STT 실행
```
[라즈베리파이 Python 3.10]
├─ 마이크 상태: STT 목적 음성 수집 ON (4초간 수집)
├─ 버퍼링 STT 실행 (GCP STT)
└─ STT 완료 후:
    ├─ 마이크 상태: STT 목적 음성 수집 OFF (mic.pause())
    └─ 소켓 이벤트 전송:
        └─ 브리지 서버 → 브리지 클라이언트 → FastAPI
           이벤트: stt_result
           데이터: {
               "type": "final",
               "text": "사용자 질문",
               "confidence": 0.95,
               "session_id": null  // 버퍼링 STT는 세션 ID 없음
           }

[FastAPI]
├─ 이벤트 수신: stt_result (버퍼링 STT)
├─ Intent 분류 (Gemini-Flash)
└─ 소켓 이벤트 전송:
    └─ 모바일로
       이벤트: intent_result
       데이터: {
           "intent": "AI_SUPPORTER" | "OPERATOR",
           "text": "사용자 질문",
           "confidence": 0.95
       }
```

---

### 📍 케이스 2: AI_SUPPORTER 경로 - CV 탐지 성공

#### 2-1. Intent 분류 후 (AI_SUPPORTER)
```
[모바일]
├─ 이벤트 수신: intent_result (intent: "AI_SUPPORTER")
├─ 음성 파일 재생: "001_AI_Supporter_기능을_시작합니다_오류_탐지.mp3"
└─ 재생 완료 후 소켓 이벤트 전송:
    └─ FastAPI로
       이벤트: intent_audio_completed
       데이터: {"intent": "AI_SUPPORTER", "timestamp": ...}

[FastAPI]
├─ 이벤트 수신: intent_audio_completed (intent: "AI_SUPPORTER")
├─ CV 프레임 수집 시작
├─ CV 모델 실행 (device_best.pt → module_best.pt → anomaly_detector)
└─ CV 결과 확인
```

#### 2-2. CV 탐지 성공
```
[FastAPI]
├─ CV 탐지 성공 (detected: true)
├─ GPT-4o로 최종 답변 생성
│   └─ 소켓 이벤트 전송:
│       └─ 라즈베리파이로
│          이벤트: mic_off
│          데이터: {}
│          목적: STT 목적 음성 수집 중지 (이미 OFF 상태이지만 명시적으로 전송)
├─ TTS 변환
└─ 소켓 이벤트 전송:
    └─ 모바일로
       이벤트: final_answer
       데이터: {
           "session_id": null,
           "turn_id": 1,
           "status": "completed",
           "answer": "최종 답변",
           "audio_content": "base64_encoded_audio",
           "audio_encoding": "audio/mpeg",
           "cv_detection_result": {...}
       }

[라즈베리파이]
├─ 이벤트 수신: mic_off
│   └─ 처리: mic.pause() (이미 OFF 상태일 수 있음)
└─ 이벤트 수신: cv_detection_success
    └─ 처리: 로그만 출력 (마이크는 OFF 상태 유지)

[모바일]
├─ 이벤트 수신: final_answer
├─ TTS 재생
└─ 재생 완료 후 소켓 이벤트 전송:
    └─ FastAPI로
       이벤트: audio_playback_completed
       데이터: {"type": "final_answer", "timestamp": ...}

[FastAPI]
├─ 이벤트 수신: audio_playback_completed (type: "final_answer")
└─ 소켓 이벤트 전송:
    ├─ 라즈베리파이로
    │   이벤트: mic_on
    │   데이터: {}
    │   목적: STT 목적 음성 수집 재개
    └─ 라즈베리파이로
        이벤트: wakeword_start_waiting
        데이터: {}
        목적: Wakeword 감지 대기 시작

[라즈베리파이]
├─ 이벤트 수신: mic_on
│   └─ 처리: mic.resume() (STT 목적 음성 수집 재개)
└─ 이벤트 수신: wakeword_start_waiting
    └─ 처리:
        ├─ wakeword_detector.resume()
        └─ mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)

[최종 상태]
├─ 마이크 상태: STT 목적 음성 수집 ON
├─ Wakeword 감지: 활성화
└─ 상태: Wakeword 감지 대기 중 (초기 상태로 복귀)
```

---

### 📍 케이스 3: AI_SUPPORTER 경로 - CV 탐지 실패 → Streaming STT → Clarify → GPT-4o

#### 3-1. CV 탐지 실패
```
[FastAPI]
├─ CV 탐지 실패 (detected: false)
└─ 소켓 이벤트 전송:
    ├─ 모바일로
    │   이벤트: cv_detection_failed
    │   데이터: {"message": "오류를 탐지하지 못했습니다..."}
    └─ 라즈베리파이로
        이벤트: cv_detection_failed
        데이터: {"message": "Streaming STT 세션을 시작하세요."}

[모바일]
├─ 이벤트 수신: cv_detection_failed
├─ 음성 파일 재생: "001_오류를_탐지하지_못했습니다_AI_Supporter와의.mp3"
└─ 재생 완료 후 소켓 이벤트 전송:
    └─ FastAPI로
       이벤트: audio_playback_completed
       데이터: {"type": "cv_detection_failed", "timestamp": ...}

[FastAPI]
├─ 이벤트 수신: audio_playback_completed (type: "cv_detection_failed")
└─ 소켓 이벤트 전송:
    └─ 라즈베리파이로
       이벤트: start_streaming_stt
       데이터: {
           "session_id": "uuid",
           "message": "Streaming STT 세션을 시작하세요."
       }

[라즈베리파이]
├─ 이벤트 수신: start_streaming_stt
├─ 마이크 상태: STT 목적 음성 수집 ON (mic.resume() - 이미 ON일 수 있음)
└─ Streaming STT 세션 시작
```

#### 3-2. Streaming STT 실행 중
```
[라즈베리파이 Python 3.10]
├─ 마이크 상태: STT 목적 음성 수집 ON
├─ Streaming STT 실행 중 (GCP STT)
└─ 소켓 이벤트 전송 (사용자 음성 입력 시):
    └─ 브리지 서버 → 브리지 클라이언트 → FastAPI
       이벤트: stt_result
       데이터: {
           "type": "interim" | "final",
           "text": "사용자 질문",
           "confidence": 0.95,
           "session_id": "uuid"  // Streaming STT는 세션 ID 있음
       }

[FastAPI]
├─ 이벤트 수신: stt_result (Streaming STT, type: "final")
├─ Clarify 처리 (process_clarify_qa_turn)
│   ├─ RAG 검색
│   ├─ Evidence Check
│   └─ 분기:
│       ├─ RED/YELLOW → Clarify 질문 생성
│       └─ GREEN → GPT-4o로 최종 답변 생성
└─ 소켓 이벤트 전송:
    └─ 모바일로
       이벤트: clarify_qa_turn (RED/YELLOW) 또는 final_answer (GREEN)
       데이터: {...}
```

#### 3-3. Clarify Q&A 턴 (RED/YELLOW)
```
[모바일]
├─ 이벤트 수신: clarify_qa_turn
├─ TTS 재생
└─ 재생 완료 후 소켓 이벤트 전송:
    └─ FastAPI로
       이벤트: audio_playback_completed
       데이터: {
           "type": "clarify_qa_turn",
           "session_id": "uuid",
           "turn_id": 1
       }

[FastAPI]
├─ 이벤트 수신: audio_playback_completed (type: "clarify_qa_turn")
└─ 처리: 다음 Streaming STT 질문 대기 (별도 처리 없음)

[라즈베리파이]
└─ Streaming STT 계속 실행 중 (다음 질문 대기)
```

#### 3-4. 최종 답변 생성 (GREEN)
```
[FastAPI]
├─ Evidence Check 결과: GREEN
├─ GPT-4o 호출
│   └─ 소켓 이벤트 전송:
│       └─ 라즈베리파이로
│          이벤트: mic_off
│          데이터: {}
│          목적: STT 목적 음성 수집 중지
├─ GPT-4o로 최종 답변 생성
├─ TTS 변환
└─ 소켓 이벤트 전송:
    └─ 모바일로
       이벤트: final_answer
       데이터: {
           "session_id": "uuid",
           "turn_id": 1,
           "status": "completed",
           "answer": "최종 답변",
           "audio_content": "base64_encoded_audio",
           "audio_encoding": "audio/mpeg"
       }

[라즈베리파이]
├─ 이벤트 수신: mic_off
│   └─ 처리: mic.pause() (STT 목적 음성 수집 중지)
└─ Streaming STT 세션 종료

[모바일]
├─ 이벤트 수신: final_answer
├─ TTS 재생
└─ 재생 완료 후 소켓 이벤트 전송:
    └─ FastAPI로
       이벤트: audio_playback_completed
       데이터: {"type": "final_answer", "timestamp": ...}

[FastAPI]
├─ 이벤트 수신: audio_playback_completed (type: "final_answer")
└─ 소켓 이벤트 전송:
    ├─ 라즈베리파이로
    │   이벤트: mic_on
    │   데이터: {}
    │   목적: STT 목적 음성 수집 재개
    └─ 라즈베리파이로
        이벤트: wakeword_start_waiting
        데이터: {}
        목적: Wakeword 감지 대기 시작

[라즈베리파이]
├─ 이벤트 수신: mic_on
│   └─ 처리: mic.resume() (STT 목적 음성 수집 재개)
└─ 이벤트 수신: wakeword_start_waiting
    └─ 처리:
        ├─ wakeword_detector.resume()
        └─ mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)

[최종 상태]
├─ 마이크 상태: STT 목적 음성 수집 ON
├─ Wakeword 감지: 활성화
└─ 상태: Wakeword 감지 대기 중 (초기 상태로 복귀)
```

---

### 📍 케이스 4: OPERATOR 경로

#### 4-1. Intent 분류 후 (OPERATOR)
```
[모바일]
├─ 이벤트 수신: intent_result (intent: "OPERATOR")
├─ 음성 파일 재생: "002_Operator_기능을_시작합니다_통신_연결을_시작합니다.mp3"
└─ 재생 완료 후 소켓 이벤트 전송:
    └─ FastAPI로
       이벤트: intent_audio_completed
       데이터: {"intent": "OPERATOR", "timestamp": ...}

[FastAPI]
├─ 이벤트 수신: intent_audio_completed (intent: "OPERATOR")
└─ 소켓 이벤트 전송:
    └─ 라즈베리파이 별도 프로세스로
       이벤트: handle_audio_stream
       데이터: {"start": True}
       목적: WebRTC 오디오 스트리밍 목적으로 음성 수집 시작

[라즈베리파이 별도 프로세스] (raspi/app/sockets/socket_manager.py)
├─ 이벤트 수신: handle_audio_stream (start: True)
└─ 처리:
    └─ AudioService.start_streaming()
       └─ WebRTC 오디오 스트리밍 목적으로 음성 수집 시작
       └─ 소켓 이벤트 전송 (지속적으로):
           └─ FastAPI로
              이벤트: audio_frame
              데이터: binary_audio_data
```

#### 4-2. WebRTC 오디오 스트리밍 실행 중
```
[라즈베리파이]
├─ Python 3.10 프로세스:
│   └─ 마이크 상태: STT 목적 음성 수집 OFF (버퍼링 STT 후 OFF 상태)
└─ 별도 프로세스 (raspi/app/sockets/socket_manager.py):
    ├─ 마이크 상태: WebRTC 오디오 스트리밍 목적 음성 수집 ON (AudioService)
    └─ 소켓 이벤트 전송 (지속적으로):
        └─ FastAPI로
           이벤트: audio_frame
           데이터: binary_audio_data

[FastAPI]
├─ 이벤트 수신: audio_frame
└─ 소켓 이벤트 전송:
    └─ 웹으로
       이벤트: audio_frame
       데이터: binary_audio_data
```

#### 4-3. 통신 종료
```
[웹]
└─ 소켓 이벤트 전송:
    └─ FastAPI로
       이벤트: communication_close
       데이터: null

[FastAPI]
├─ 이벤트 수신: communication_close
└─ 소켓 이벤트 전송:
    ├─ 라즈베리파이 별도 프로세스로
    │   이벤트: handle_audio_stream
    │   데이터: {"start": False}
    │   목적: WebRTC 오디오 스트리밍 목적 음성 수집 중지
    └─ 라즈베리파이 Python 3.13 프로세스로
        이벤트: wakeword_start_waiting
        데이터: {}
        목적: Wakeword 감지 대기 시작

[라즈베리파이]
├─ 별도 프로세스 (raspi/app/sockets/socket_manager.py):
│   ├─ 이벤트 수신: handle_audio_stream (start: False)
│   └─ 처리: AudioService.stop_streaming()
│      └─ WebRTC 오디오 스트리밍 목적 음성 수집 중지
└─ Python 3.13 프로세스:
    ├─ 이벤트 수신: wakeword_start_waiting
    ├─ 브리지 클라이언트를 통해 Python 3.10 프로세스로 전달
    └─ Python 3.10 프로세스:
        └─ 처리:
            ├─ wakeword_detector.resume()
            └─ mic.enable_wakeword_callback(wakeword_detector.process_audio_chunk)

[최종 상태]
├─ 마이크 상태: STT 목적 음성 수집 ON (Wakeword 감지 대기)
├─ Wakeword 감지: 활성화
└─ 상태: Wakeword 감지 대기 중 (초기 상태로 복귀)
```

---

### 📍 케이스 5: WebRTC 통신 요청 수락 (AI_Supporter/OPERATOR 실행 중)

#### 5-1. 웹에서 모바일로 통신 요청
```
[웹]
└─ HTTP 요청:
    └─ Spring 서버로
       POST /api/webrtc/request
       데이터: {senderAccountId, receiverAccountId, ...}

[Spring 서버]
└─ SSE 이벤트 전송:
    └─ 모바일로
       이벤트: callRequest
       데이터: {senderInfo, ...}

[모바일]
├─ 이벤트 수신: callRequest
├─ 통신 수락/거절 UI 표시
└─ 수락 시:
    └─ HTTP 요청:
        └─ Spring 서버로
           POST /api/webrtc/response
           데이터: {acceptConnection: true, ...}
```

#### 5-2. 모바일에서 통신 수락
```
[모바일]
└─ 소켓 이벤트 전송:
    └─ FastAPI로
       이벤트: accept_communication
       데이터: null

[FastAPI]
├─ 이벤트 수신: accept_communication
├─ 현재 실행 중인 Streaming STT 세션 확인
│   └─ 있으면:
│       ├─ 소켓 이벤트 전송:
│       │   └─ 라즈베리파이 Python 3.13 프로세스로
│       │      이벤트: stop_streaming_stt
│       │      데이터: {
│       │          "session_id": "uuid",
│       │          "reason": "통신 요청 수락으로 인한 중지"
│       │      }
│       └─ clarify_sessions.clear()
├─ 소켓 이벤트 전송:
│   └─ 라즈베리파이 Python 3.13 프로세스로
│      이벤트: mic_off
│      데이터: {}
│      목적: STT 목적 음성 수집 중지
└─ 소켓 이벤트 전송:
    └─ 라즈베리파이 별도 프로세스로
       이벤트: handle_audio_stream
       데이터: {"start": True}
       목적: WebRTC 오디오 스트리밍 목적으로 음성 수집 시작

[라즈베리파이]
├─ Python 3.13 프로세스:
│   ├─ 이벤트 수신: stop_streaming_stt
│   │   └─ 브리지 클라이언트를 통해 Python 3.10 프로세스로 전달
│   │   └─ Python 3.10 프로세스:
│   │       └─ 처리:
│   │           ├─ Streaming STT 세션 종료
│   │           └─ mic.pause() (STT 목적 음성 수집 중지)
│   └─ 이벤트 수신: mic_off
│       └─ 브리지 클라이언트를 통해 Python 3.10 프로세스로 전달
│       └─ Python 3.10 프로세스:
│           └─ 처리: mic.pause() (STT 목적 음성 수집 중지 - 중복일 수 있음)
└─ 별도 프로세스 (raspi/app/sockets/socket_manager.py):
    ├─ 이벤트 수신: handle_audio_stream (start: True)
    └─ 처리: AudioService.start_streaming()
       └─ WebRTC 오디오 스트리밍 목적으로 음성 수집 시작
```

#### 5-3. 통신 종료 (케이스 4-3과 동일)
```
[웹]
└─ 소켓 이벤트 전송:
    └─ FastAPI로
       이벤트: communication_close
       데이터: null

[FastAPI]
└─ 소켓 이벤트 전송:
    ├─ 라즈베리파이 별도 프로세스로
    │   이벤트: handle_audio_stream
    │   데이터: {"start": False}
    └─ 라즈베리파이 Python 3.13 프로세스로
        이벤트: wakeword_start_waiting
        데이터: {}

[라즈베리파이]
├─ 별도 프로세스 (raspi/app/sockets/socket_manager.py):
│   ├─ 이벤트 수신: handle_audio_stream (start: False)
│   └─ 처리: AudioService.stop_streaming()
└─ Python 3.13 프로세스:
    ├─ 이벤트 수신: wakeword_start_waiting
    ├─ 브리지 클라이언트를 통해 Python 3.10 프로세스로 전달
    └─ Python 3.10 프로세스:
        └─ 처리: Wakeword 감지 대기 시작

[최종 상태]
├─ 마이크 상태: STT 목적 음성 수집 ON
├─ Wakeword 감지: 활성화
└─ 상태: Wakeword 감지 대기 중
```

---

## 📊 소켓 이벤트 목록

### 라즈베리파이 → FastAPI

| 이벤트명 | 데이터 | 목적 | 경로 |
|---------|--------|------|------|
| `wakeword_detected` | `{}` | Wakeword 감지 알림 | 브리지 서버 → 브리지 클라이언트 → FastAPI |
| `stt_result` | `{"type": "final\|interim", "text": "...", "confidence": 0.95, "session_id": "uuid"\|null}` | STT 결과 전송 | 브리지 서버 → 브리지 클라이언트 → FastAPI |
| `audio_frame` | `binary_audio_data` | WebRTC 오디오 스트리밍 | 라즈베리파이 → FastAPI → 웹 |

### FastAPI → 라즈베리파이

| 이벤트명 | 데이터 | 목적 | 시점 |
|---------|--------|------|------|
| `start_streaming_stt` | `{"session_id": "uuid", "message": "..."}` | Streaming STT 세션 시작 | CV 탐지 실패 후 |
| `stop_streaming_stt` | `{"session_id": "uuid", "reason": "..."}` | Streaming STT 세션 종료 | 통신 요청 수락 시 |
| `mic_off` | `{}` | STT 목적 음성 수집 중지 | GPT-4o 호출 시, 통신 요청 수락 시 |
| `mic_on` | `{}` | STT 목적 음성 수집 재개 | 최종 답변 TTS 재생 완료 후 |
| `wakeword_start_waiting` | `{}` | Wakeword 감지 대기 시작 | 통신 종료 후, 최종 답변 TTS 재생 완료 후 |
| `cv_detection_failed` | `{"message": "..."}` | CV 탐지 실패 알림 | CV 탐지 실패 시 |
| `cv_detection_success` | `"message"` | CV 탐지 성공 알림 | CV 탐지 성공 시 |
| `handle_audio_stream` | `{"start": True\|False}` | WebRTC 오디오 스트리밍 목적 음성 수집 시작/중지 | OPERATOR Intent 재생 완료 후, 통신 요청 수락 시, 통신 종료 시 |

### FastAPI → 모바일

| 이벤트명 | 데이터 | 목적 | 시점 |
|---------|--------|------|------|
| `wakeword_detected` | `{"timestamp": null}` | 모바일 음성 파일 재생 시작 | Wakeword 감지 후 |
| `intent_result` | `{"intent": "AI_SUPPORTER\|OPERATOR", "text": "...", "confidence": 0.95}` | Intent 분류 결과 | 버퍼링 STT 완료 후 |
| `cv_detection_failed` | `{"message": "..."}` | CV 탐지 실패 알림 | CV 탐지 실패 시 |
| `final_answer` | `{"session_id": "uuid"\|null, "turn_id": 1, "status": "completed", "answer": "...", "audio_content": "...", ...}` | 최종 답변 전송 | GPT-4o 답변 생성 후 |
| `clarify_qa_turn` | `{"session_id": "uuid", "turn_id": 1, "user_question": "...", "llm_answer": "...", "audio_content": "...", "need_clarify": true, ...}` | Clarify 질문/답변 턴 | Clarify 처리 후 |

### 모바일 → FastAPI

| 이벤트명 | 데이터 | 목적 | 시점 |
|---------|--------|------|------|
| `wakeword_audio_completed` | `{"timestamp": ...}` | Wakeword 음성 파일 재생 완료 | Wakeword 음성 파일 재생 완료 후 |
| `intent_audio_completed` | `{"intent": "AI_SUPPORTER\|OPERATOR", "timestamp": ...}` | Intent 음성 파일 재생 완료 | Intent 음성 파일 재생 완료 후 |
| `audio_playback_completed` | `{"type": "cv_detection_failed\|clarify_qa_turn\|final_answer", "session_id": "uuid", "turn_id": 1, "timestamp": ...}` | 오디오 재생 완료 | 각종 TTS 재생 완료 후 |

### 웹 → FastAPI

| 이벤트명 | 데이터 | 목적 | 시점 |
|---------|--------|------|------|
| `accept_communication` | `null` | 통신 요청 수락 | 모바일에서 통신 수락 후 |
| `communication_close` | `null` | 통신 종료 | 웹에서 통신 종료 버튼 클릭 시 |

---

## 🎤 마이크 상태 변화 타임라인

### 케이스별 마이크 상태 요약

#### 케이스 1: 초기 상태 → Wakeword → 버퍼링 STT → Intent 분류
```
초기: STT 목적 ON, Wakeword 활성화
Wakeword 감지: STT 목적 ON (Wakeword 비활성화)
버퍼링 STT 실행: STT 목적 ON
버퍼링 STT 완료: STT 목적 OFF
Intent 분류 대기: STT 목적 OFF
```

#### 케이스 2: AI_SUPPORTER - CV 탐지 성공
```
Intent 분류 완료: STT 목적 OFF
CV 탐지 실행: STT 목적 OFF
CV 탐지 성공: STT 목적 OFF (유지)
GPT-4o 호출: STT 목적 OFF (명시적 전송)
최종 답변 TTS 재생 완료: STT 목적 ON, Wakeword 활성화
```

#### 케이스 3: AI_SUPPORTER - CV 탐지 실패 → Streaming STT
```
Intent 분류 완료: STT 목적 OFF
CV 탐지 실패: STT 목적 OFF
Streaming STT 시작: STT 목적 ON
Streaming STT 실행 중: STT 목적 ON
GPT-4o 호출: STT 목적 OFF
최종 답변 TTS 재생 완료: STT 목적 ON, Wakeword 활성화
```

#### 케이스 4: OPERATOR
```
Intent 분류 완료: STT 목적 OFF
Intent 음성 파일 재생 완료: STT 목적 OFF
WebRTC 오디오 스트리밍 시작: WebRTC 목적 ON (STT 목적은 OFF)
통신 종료: WebRTC 목적 OFF, STT 목적 ON, Wakeword 활성화
```

#### 케이스 5: WebRTC 통신 요청 수락 (AI_Supporter/OPERATOR 실행 중)
```
실행 중: STT 목적 ON 또는 OFF (상태에 따라)
통신 요청 수락: STT 목적 OFF, WebRTC 목적 ON
통신 종료: WebRTC 목적 OFF, STT 목적 ON, Wakeword 활성화
```

---

## 🔑 핵심 포인트

1. **마이크는 하나**: 시점별로 음성을 어디에 활용하는지만 다름
2. **STT 목적**: `MicStream`을 통해 GCP STT로 전송하거나 Wakeword 감지에 사용
3. **WebRTC 오디오 스트리밍 목적**: `AudioService`를 통해 Socket.IO `audio_frame` 이벤트로 전송
4. **Wakeword 감지**: Wakeword 감지 후 즉시 비활성화, 서비스 완료 후 재활성화
5. **마이크 상태 전환**: 
   - STT 목적: `mic.pause()` / `mic.resume()` (MicStream)
   - WebRTC 목적: `AudioService.stop_streaming()` / `AudioService.start_streaming()`

