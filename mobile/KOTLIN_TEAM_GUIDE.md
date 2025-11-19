# 코틀린 팀원 작업 가이드

## 📋 목차
1. [전체 플로우 개요](#전체-플로우-개요)
2. [FastAPI → 모바일 이벤트 및 데이터 구조](#fastapi--모바일-이벤트-및-데이터-구조)
3. [구현해야 할 부분](#구현해야-할-부분)
4. [데이터 타입 및 필드 상세](#데이터-타입-및-필드-상세)
5. [코드 예시](#코드-예시)

---

## 전체 플로우 개요

```
CV 탐지 성공
  ↓
[1단계] 간단한 알림 생성 및 전송 (cv_detection_anomaly)
  ↓
모바일: 알림 TTS 재생 → 모달 표시 ("답변 생성 중...")
  ↓
[2단계] 전체 정비 가이드 생성 및 전송 (final_answer)
  ↓
모바일: 모달 숨김
  ↓
모바일: 각 섹션별 마크다운 말풍선 표시 + 오디오 재생
  1. possible_causes (원인) → 마크다운 표시 + 오디오 재생
  2. 2초 대기
  3. recommended_actions (조치) → 마크다운 표시 + 오디오 재생
  4. 2초 대기
  5. safety_warnings (주의사항) → 마크다운 표시 + 오디오 재생
  ↓
마지막 섹션 완료 → 서비스 종료 처리
```

---

## FastAPI → 모바일 이벤트 및 데이터 구조

### 1단계: CV 탐지 알림 (`cv_detection_anomaly`)

**이벤트명**: `cv_detection_anomaly`

**수신 위치**: `WorkingActivity.kt`의 `handleCvDetectionAnomaly(cvAnomaly: CvDetectionAnomalyDto)`

**데이터 구조**:
```kotlin
data class CvDetectionAnomalyDto(
    val message: String,  // 간단한 탐지 알림 메시지
    val audio_content: String? = null,  // base64 인코딩된 오디오
    val audio_encoding: String? = null,  // "audio/mpeg"
    val cv_detection_result: CvDetectionResultDto? = null
)

data class CvDetectionResultDto(
    val device_type: String,  // 예: "AHU"
    val modules: List<Any>? = null,
    val anomalies: Map<String, Any>? = null,
    val message: String? = null
)
```

**JSON 예시**:
```json
{
    "message": "AHU에서 게이지의 압력 과다 오류가 탐지되었습니다.",
    "audio_content": "UklGRiQAAABXQVZFZm10...",
    "audio_encoding": "audio/mpeg",
    "cv_detection_result": {
        "device_type": "AHU",
        "modules": [...],
        "anomalies": {
            "gauge": {
                "status": "anomaly",
                "detail": "pressure_high",
                ...
            }
        },
        "message": "OK"
    }
}
```

**처리 방법**:
- `message` 텍스트를 UI에 표시
- `audio_content`가 있으면 TTS 재생
- TTS 재생 완료 후:
  - 모달 표시: `showModal("답변 생성 중...")`
  - `sendCvDetectionAnomalyAudioCompleted()` 호출

**현재 구현 상태**: ✅ 완료 (`WorkingActivity.kt` 590-640줄)

---

### 2단계: 전체 정비 가이드 (`final_answer`)

**이벤트명**: `final_answer`

**수신 위치**: `WorkingActivity.kt`의 `handleFinalAnswerFromSocket(finalAnswer: FinalAnswerDto)`

**데이터 구조**:
```kotlin
data class FinalAnswerDto(
    val session_id: String,
    val turn_id: Int,
    val status: String,  // "completed"
    val answer: String,  // TTS 친화적 요약 텍스트
    val audio_content: String? = null,  // null (각 섹션별로 분리됨)
    val audio_encoding: String? = null,  // null
    val structured_answer: Map<String, Any>? = null,  // ⭐ 핵심 데이터
    val citations: List<Citation>? = null
)
```

**처리 방법**:
- 모달 숨김: `hideModal()`
- `structured_answer`가 있으면 `handleStructuredAnswerSections()` 호출

**현재 구현 상태**: ✅ 완료 (`WorkingActivity.kt` 799-833줄)

---

## 데이터 타입 및 필드 상세

### `structured_answer` 필드 전체 구조

```kotlin
val structuredAnswer: Map<String, Any>? = finalAnswer.structured_answer
```

#### 기본 정보 필드

| 필드명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `error_code` | `String?` | 오류 코드 | `"gauge.pressure_high"` |
| `markdown_text` | `String?` | 전체 마크다운 원본 | `"# 🔧 gauge.pressure_high\n\n## 🟥 원인\n..."` |
| `query` | `String?` | RAG 검색 쿼리 | `"AHU에서 gauge.pressure_high에서 이상이 탐지되었습니다"` |
| `tts_text` | `String?` | TTS 친화적 전체 요약 | `"gauge.pressure_high에 대한 정비 가이드입니다..."` |
| `citations` | `List<Map<String, Any>>?` | 출처 정보 | `[{"section": "...", "pages": [45, 46], ...}]` |

#### TTS 변환용 필드 (리스트 형태)

| 필드명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `possible_causes` | `List<String>?` | 원인 목록 (TTS용) | `["필터 막힘...", "댐퍼 과도..."]` |
| `recommended_actions` | `List<Map<String, Any>>?` | 조치 목록 (TTS용) | `[{"action": "...", "priority": "medium"}, ...]` |
| `safety_warnings` | `List<String>?` | 주의사항 목록 (TTS용) | `["압력 1.5bar...", ...]` |

#### 모바일 렌더링용 필드 (마크다운 형태) ⭐

| 필드명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `possible_causes_markdown` | `String?` | 원인 섹션 마크다운 | `"## 🟥 원인\n- 필터 막힘...\n- 댐퍼..."` |
| `recommended_actions_markdown` | `String?` | 조치 섹션 마크다운 | `"## 🛠 조치\n1. 프리필터...\n2. 댐퍼..."` |
| `safety_warnings_markdown` | `String?` | 주의사항 섹션 마크다운 | `"## ⚠ 주의사항\n- 압력 1.5bar..."` |

#### 각 섹션별 오디오 필드

| 필드명 | 타입 | 설명 | 예시 |
|--------|------|------|------|
| `possible_causes_audio` | `String?` | 원인 섹션 오디오 (base64) | `"UklGRiQAAABXQVZFZm10..."` |
| `possible_causes_audio_encoding` | `String?` | 원인 섹션 오디오 인코딩 | `"audio/mpeg"` |
| `recommended_actions_audio` | `String?` | 조치 섹션 오디오 (base64) | `"UklGRiQAAABXQVZFZm10..."` |
| `recommended_actions_audio_encoding` | `String?` | 조치 섹션 오디오 인코딩 | `"audio/mpeg"` |
| `safety_warnings_audio` | `String?` | 주의사항 섹션 오디오 (base64) | `"UklGRiQAAABXQVZFZm10..."` |
| `safety_warnings_audio_encoding` | `String?` | 주의사항 섹션 오디오 인코딩 | `"audio/mpeg"` |

---

## 각 섹션별 마크다운 텍스트 예시

### 섹션 1: possible_causes_markdown (원인)

```markdown
## 🟥 원인

- 필터 막힘으로 인한 풍량 저하
- 댐퍼 과도 개방
- 인버터 RPM 과상승
```

### 섹션 2: recommended_actions_markdown (조치)

```markdown
## 🛠 조치

1. 프리필터 차압 측정 후 기준 초과 시 교체
2. 댐퍼 개도 70% 이하로 조정 후 압력 확인
3. 인버터 출력 주파수 확인 (40~60Hz)
```

### 섹션 3: safety_warnings_markdown (주의사항)

```markdown
## ⚠ 주의사항

- 압력 1.5bar 이상 지속 시 팬 과부하 위험
- 필터 교체 후에도 동일하면 배관 이물질 가능성 점검
```

---

## 구현해야 할 부분

### 위치: `WorkingActivity.kt` (930-941줄)

**현재 코드**:
```kotlin
// 마크다운 말풍선 표시 (코틀린 팀원이 구현할 부분)
runOnUiThread {
    // TODO: 코틀린 팀원이 각 섹션별 마크다운 말풍선 UI 구현
    // markdownText를 Markwon 라이브러리로 렌더링하여 말풍선에 표시
    // 예시: showSectionBubbleWithMarkdown(sectionName, markdownText)
    if (markdownText != null && markdownText.isNotBlank()) {
        Log.i(TAG, "💬 [UI] $sectionName 마크다운 말풍선 표시")
        Log.i(TAG, "   마크다운 텍스트: ${markdownText.take(100)}...")
    } else {
        Log.w(TAG, "⚠️ [UI] $sectionName 마크다운 텍스트가 없습니다")
    }
}
```

**구현해야 할 내용**:
1. `markdownText`를 Markwon 라이브러리로 렌더링
2. 각 섹션별 말풍선 UI에 마크다운 표시
3. 섹션별 스타일 적용 (원인/조치/주의사항 구분)

---

## 코드 예시

### 1. Markwon 라이브러리 설정

**의존성 추가** (`mobile/app/build.gradle`):
```gradle
dependencies {
    // Markwon - 마크다운 렌더링 라이브러리
    implementation 'io.noties:markwon:4.6.2'
    implementation 'io.noties:markwon-core:4.6.2'
}
```

**Markwon 초기화** (`WorkingActivity.kt`):
```kotlin
import io.noties.markwon.Markwon
import io.noties.markwon.core.CorePlugin

class WorkingActivity : AppCompatActivity() {
    private lateinit var markwon: Markwon
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Markwon 초기화
        markwon = Markwon.builder(this)
            .usePlugin(CorePlugin.create())
            .build()
    }
}
```

### 2. processSection() 함수에서 마크다운 렌더링

```kotlin
private suspend fun processSection(
    sectionName: String,
    markdownText: String?,
    audioContent: String?,
    audioEncoding: String?,
    isLastSection: Boolean,
    onComplete: suspend () -> Unit
) {
    // 마크다운 말풍선 표시
    runOnUiThread {
        if (markdownText != null && markdownText.isNotBlank()) {
            // 방법 1: 별도 TextView에 렌더링
            val markdownTextView = findViewById<TextView>(R.id.sectionMarkdownTextView)
            markwon.setMarkdown(markdownTextView, markdownText)
            
            // 방법 2: 말풍선 UI에 렌더링
            showSectionBubbleWithMarkdown(sectionName, markdownText)
        }
    }
    
    // 오디오 재생 (기존 코드 유지)
    // ...
}

// 말풍선 UI에 마크다운 표시하는 함수 예시
private fun showSectionBubbleWithMarkdown(sectionName: String, markdownText: String) {
    // 1. 말풍선 View 생성 또는 가져오기
    val bubbleView = createOrGetBubbleView(sectionName)
    
    // 2. TextView 찾기 (말풍선 내부)
    val textView = bubbleView.findViewById<TextView>(R.id.bubbleMarkdownText)
    
    // 3. Markwon으로 마크다운 렌더링
    markwon.setMarkdown(textView, markdownText)
    
    // 4. 섹션별 스타일 적용
    when (sectionName) {
        "원인" -> {
            // 원인 섹션 스타일 (예: 빨간색 테두리)
            bubbleView.setBackgroundResource(R.drawable.bubble_causes)
        }
        "조치" -> {
            // 조치 섹션 스타일 (예: 파란색 테두리)
            bubbleView.setBackgroundResource(R.drawable.bubble_actions)
        }
        "주의사항" -> {
            // 주의사항 섹션 스타일 (예: 노란색 테두리)
            bubbleView.setBackgroundResource(R.drawable.bubble_warnings)
        }
    }
    
    // 5. 말풍선을 화면에 표시
    addBubbleToView(bubbleView)
}
```

### 3. 데이터 추출 예시

```kotlin
private fun handleStructuredAnswerSections(structuredAnswer: Map<String, Any>) {
    // 1. possible_causes (원인) - 마크다운 텍스트 + 오디오
    val possibleCausesMarkdown = structuredAnswer["possible_causes_markdown"] as? String
    val possibleCausesAudio = structuredAnswer["possible_causes_audio"] as? String
    val possibleCausesAudioEncoding = structuredAnswer["possible_causes_audio_encoding"] as? String

    // 2. recommended_actions (조치) - 마크다운 텍스트 + 오디오
    val recommendedActionsMarkdown = structuredAnswer["recommended_actions_markdown"] as? String
    val recommendedActionsAudio = structuredAnswer["recommended_actions_audio"] as? String
    val recommendedActionsAudioEncoding = structuredAnswer["recommended_actions_audio_encoding"] as? String

    // 3. safety_warnings (주의사항) - 마크다운 텍스트 + 오디오
    val safetyWarningsMarkdown = structuredAnswer["safety_warnings_markdown"] as? String
    val safetyWarningsAudio = structuredAnswer["safety_warnings_audio"] as? String
    val safetyWarningsAudioEncoding = structuredAnswer["safety_warnings_audio_encoding"] as? String

    // 각 섹션별 처리 (순차적으로)
    processSection(
        sectionName = "원인",
        markdownText = possibleCausesMarkdown,  // ⭐ 마크다운 텍스트
        audioContent = possibleCausesAudio,
        audioEncoding = possibleCausesAudioEncoding,
        isLastSection = false
    ) {
        // ...
    }
}
```

---

## 실제 JSON 데이터 예시

### `final_answer` 이벤트 전체 구조

```json
{
    "session_id": null,
    "turn_id": 1,
    "status": "completed",
    "answer": "AHU에서 gauge.pressure_high에 대한 정비 가이드입니다...",
    "structured_answer": {
        "error_code": "gauge.pressure_high",
        "markdown_text": "# 🔧 gauge.pressure_high\n\n## 🟥 원인\n- 필터 막힘으로 인한 풍량 저하\n- 댐퍼 과도 개방\n\n## 🛠 조치\n1. 프리필터 차압 측정 후 기준 초과 시 교체\n2. 댐퍼 개도 70% 이하로 조정\n\n## ⚠ 주의사항\n- 압력 1.5bar 이상 지속 시 팬 과부하 위험",
        
        "possible_causes_markdown": "## 🟥 원인\n\n- 필터 막힘으로 인한 풍량 저하\n- 댐퍼 과도 개방\n- 인버터 RPM 과상승",
        "possible_causes_audio": "UklGRiQAAABXQVZFZm10...",
        "possible_causes_audio_encoding": "audio/mpeg",
        
        "recommended_actions_markdown": "## 🛠 조치\n\n1. 프리필터 차압 측정 후 기준 초과 시 교체\n2. 댐퍼 개도 70% 이하로 조정 후 압력 확인\n3. 인버터 출력 주파수 확인 (40~60Hz)",
        "recommended_actions_audio": "UklGRiQAAABXQVZFZm10...",
        "recommended_actions_audio_encoding": "audio/mpeg",
        
        "safety_warnings_markdown": "## ⚠ 주의사항\n\n- 압력 1.5bar 이상 지속 시 팬 과부하 위험\n- 필터 교체 후에도 동일하면 배관 이물질 가능성 점검",
        "safety_warnings_audio": "UklGRiQAAABXQVZFZm10...",
        "safety_warnings_audio_encoding": "audio/mpeg",
        
        "tts_text": "gauge.pressure_high에 대한 정비 가이드입니다...",
        "query": "AHU에서 gauge.pressure_high에서 이상이 탐지되었습니다",
        "citations": [...]
    },
    "audio_content": null,
    "audio_encoding": null,
    "citations": [...],
    "cv_detection_result": {...}
}
```

---

## 구현 체크리스트

### 필수 구현 사항

- [ ] Markwon 라이브러리 의존성 추가 (`build.gradle`)
- [ ] Markwon 초기화 (`onCreate()`)
- [ ] `processSection()` 함수에서 마크다운 렌더링 구현
- [ ] 각 섹션별 말풍선 UI 생성/표시
- [ ] 섹션별 스타일 적용 (원인/조치/주의사항 구분)

### 선택 구현 사항

- [ ] 전체 마크다운 표시 영역 (상단 또는 별도 화면)
- [ ] "전체 보기" / "섹션별 보기" 토글 버튼
- [ ] 오디오 재생 중 말풍선 강조 표시

---

## 주의사항

1. **마크다운 텍스트는 null일 수 있음**: 항상 null 체크 필요
2. **오디오 재생과 동기화**: 오디오 재생 중에는 해당 섹션 말풍선을 강조 표시 권장
3. **섹션 간 텀**: 각 섹션 완료 후 2초 대기 (이미 구현됨)
4. **마지막 섹션 처리**: 마지막 섹션 완료 후 자동으로 서비스 종료 처리 (이미 구현됨)

---

## 참고 자료

- **Markwon 공식 문서**: https://noties.io/Markwon/
- **GitHub**: https://github.com/noties/Markwon
- **마크다운 문법**: https://www.markdownguide.org/

---

## 문의사항

구현 중 문제가 발생하면 FastAPI 팀에 문의하세요.

