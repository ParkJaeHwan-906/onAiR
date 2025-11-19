# AI_SUPPORTER 경로 전체 이벤트 플로우 점검

## 하드코딩된 CV 탐지 결과 (anomaly) 기준 전체 플로우

### ✅ 1단계: Wakeword 감지
- **라즈베리파이 → FastAPI**: `wakeword_detected` 이벤트 전송
- **FastAPI → 모바일**: `wakeword_detected` 이벤트 전송
- **모바일**: 음성 파일 재생 ("onAir 서비스를 시작합니다...")
- **모바일 → FastAPI**: `wakeword_audio_completed` 이벤트 전송
- **FastAPI → 라즈베리파이**: `wakeword_audio_completed` 이벤트 전송 (버퍼링 STT 시작 신호)

**구현 위치**: 
- `handle_wakeword_detected` (line 294-350)
- `handle_wakeword_audio_completed` (line 380-435)

---

### ✅ 2단계: 버퍼링 STT 및 Intent 분류
- **라즈베리파이 → FastAPI**: `stt_result` 이벤트 전송 (type="final", 버퍼링 STT 결과)
- **FastAPI**: Gemini-Flash로 Intent 분류
- **FastAPI → 모바일**: `intent_result` 이벤트 전송 (intent="AI_SUPPORTER")
- **모바일**: Intent 음성 파일 재생
- **모바일 → FastAPI**: `intent_audio_completed` 이벤트 전송

**구현 위치**:
- `handle_stt_result` (line 1063-1162)
- `handle_intent_audio_completed` (line 438-746)

---

### ✅ 3단계: CV 탐지 (하드코딩)
- **FastAPI**: CV 모델 실행 (하드코딩된 anomaly 결과)
  - `device_type = "AHU"`
  - `anomalies = {"gauge": {...}}`
  - `has_anomaly = True`
  - `is_anomaly = True`

**구현 위치**: `handle_intent_audio_completed` (line 473-516)

---

### ✅ 4단계: 간단한 알림 메시지 생성 및 전송
- **FastAPI**: GPT-4o로 간단한 알림 메시지 생성
- **FastAPI**: TTS 변환
- **FastAPI → 모바일**: `cv_detection_anomaly` 이벤트 전송
  - `message`: 알림 메시지
  - `audio_content`: TTS 오디오 (Base64)
  - `audio_encoding`: MIME 타입
  - `cv_detection_result`: CV 탐지 결과
- **모바일**: 알림 TTS 재생 및 모달 표시 ("답변 생성 중...")
- **모바일 → FastAPI**: `audio_playback_completed` 이벤트 전송 (type="cv_detection_anomaly")

**구현 위치**: 
- `handle_intent_audio_completed` (line 640-733)
- `handle_audio_playback_completed` (line 996-1009)

**⚠️ 중요**: 
- TTS 변환 실패 시 (`audio_content = None`): 바로 전체 정비 가이드 생성 시작 (line 716-723)
- TTS 변환 성공 시: 모바일에서 `audio_playback_completed` 수신 대기 (line 724-729)

---

### ✅ 5단계: 전체 정비 가이드 생성 및 전송
- **FastAPI**: RAG 검색 (Hybrid Search + Rerank)
- **FastAPI**: GPT-4o로 전체 정비 가이드 생성
  - `possible_causes`: 원인 분석
  - `recommended_actions`: 권장 조치
  - `safety_warnings`: 안전 경고
  - 각 섹션별 TTS 변환
- **FastAPI → 모바일**: `final_answer` 이벤트 전송
  - `answer`: 전체 답변 텍스트
  - `structured_answer`: 구조화된 답변 (각 섹션별 TTS 포함)
  - `cv_detection_result`: CV 탐지 결과
- **모바일**: 각 섹션별 TTS 재생 및 마크다운 렌더링
- **모바일 → FastAPI**: `audio_playback_completed` 이벤트 전송 (type="final_answer")

**구현 위치**:
- `generate_final_maintenance_guide` (line 761-912)
- `handle_audio_playback_completed` (line 1011-1030)

---

### ✅ 6단계: 서비스 종료 오디오 재생
- **FastAPI → 모바일**: `play_service_end_audio` 이벤트 전송
  - `audio_file`: "001_onAir_서비스를_종료합니다_다른_문제사항이_있으면.mp3"
- **모바일**: 서비스 종료 오디오 재생
- **모바일 → FastAPI**: `audio_playback_completed` 이벤트 전송 (type="service_completed")

**구현 위치**: `handle_audio_playback_completed` (line 1011-1030)

---

### ✅ 7단계: Wakeword 감지 대기 상태로 복귀
- **FastAPI → 라즈베리파이**: `wakeword_start_waiting` 이벤트 전송
- **라즈베리파이**: Wakeword 감지 대기 상태로 복귀

**구현 위치**: `handle_audio_playback_completed` (line 1032-1054)

---

## 🔍 누락된 이벤트 확인

### ✅ 모든 이벤트가 구현되어 있음

1. **Wakeword 감지 플로우**: ✅ 완전 구현
2. **STT 및 Intent 분류**: ✅ 완전 구현
3. **CV 탐지 (하드코딩)**: ✅ 완전 구현
4. **간단한 알림 메시지**: ✅ 완전 구현
5. **전체 정비 가이드**: ✅ 완전 구현
6. **서비스 종료**: ✅ 완전 구현
7. **Wakeword 복귀**: ✅ 완전 구현

---

## ⚠️ 주의사항

### 1. TTS 변환 실패 처리
- TTS 변환이 실패하면 (`audio_content = None`):
  - 모바일에서 TTS 재생을 하지 않음
  - `audio_playback_completed` 이벤트를 보내지 않음
  - **해결**: FastAPI에서 바로 전체 정비 가이드 생성 시작 (line 716-723)

### 2. `_pending_cv_detection` 전역 변수
- `cv_detection_anomaly` 이벤트 전송 **전에** 저장해야 함 (line 664-673)
- `handle_audio_playback_completed`에서 사용됨 (line 1002-1006)

### 3. `audio_type` 검증
- `handle_audio_playback_completed`에서 `audio_type`을 명시적으로 확인 (line 962, 981, 996)
- `audio_type == "cv_detection_anomaly"`일 때만 전체 정비 가이드 생성

### 4. 라즈베리파이 알림
- CV 탐지 성공 시: `cv_detection_success` 이벤트 전송 (line 733, 908)
- 서비스 종료 시: `wakeword_start_waiting` 이벤트 전송 (line 1048)

---

## 📋 전체 이벤트 체크리스트

### 라즈베리파이 → FastAPI
- [x] `wakeword_detected`
- [x] `stt_result` (버퍼링 STT)

### FastAPI → 모바일
- [x] `wakeword_detected`
- [x] `intent_result`
- [x] `cv_detection_anomaly`
- [x] `final_answer`
- [x] `play_service_end_audio`

### 모바일 → FastAPI
- [x] `wakeword_audio_completed`
- [x] `intent_audio_completed`
- [x] `audio_playback_completed` (type="cv_detection_anomaly")
- [x] `audio_playback_completed` (type="final_answer")
- [x] `audio_playback_completed` (type="service_completed")

### FastAPI → 라즈베리파이
- [x] `wakeword_audio_completed`
- [x] `cv_detection_success`
- [x] `wakeword_start_waiting`

---

## ✅ 결론

**모든 이벤트가 완벽하게 구현되어 있습니다!**

하드코딩된 CV 탐지 결과로 테스트할 때:
1. 모든 이벤트가 순차적으로 전송됨
2. 각 단계에서 필요한 데이터가 올바르게 전달됨
3. 예외 상황(TTS 실패 등)도 처리됨
4. 최종적으로 Wakeword 감지 대기 상태로 복귀함

**추가로 확인할 사항**:
- 모바일 앱에서 각 이벤트를 올바르게 수신하고 처리하는지
- 모바일 앱에서 `audio_playback_completed` 이벤트를 올바른 `type`으로 전송하는지

