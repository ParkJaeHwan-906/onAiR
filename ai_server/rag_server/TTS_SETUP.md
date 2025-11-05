# TTS (Text-to-Speech) 사용 가이드

## 📋 개요

GCP TTS를 사용하여 텍스트를 음성 파일로 변환합니다.
- FastAPI 서버에서 음성 파일 생성
- Base64 인코딩된 오디오 데이터를 모바일로 전송
- 모바일에서 재생

## 🔧 설정

### 1. GCP 서비스 계정 키 설정

GCP TTS JSON 키 파일을 다운로드하고 `credentials/` 폴더에 배치합니다.

**1단계: 파일 배치**
```
rag_server/
  └── credentials/
      └── gcp-tts-key.json  ← 여기에 배치
```

**2단계: .env 파일 설정**
```env
# 상대 경로 사용 (권장)
GCP_TTS_CREDENTIALS_PATH=credentials/gcp-tts-key.json

# 또는 절대 경로 사용
# GCP_TTS_CREDENTIALS_PATH=/absolute/path/to/gcp-tts-key.json
```

**또는 환경 변수로 설정:**
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account-key.json
```

**보안 주의사항:**
- `credentials/` 폴더의 파일은 `.gitignore`에 포함되어 Git에 커밋되지 않습니다
- EC2 배포 시에는 시크릿 관리 시스템 사용 권장

### 2. 음성 설정 (선택사항)

```env
# 기본값 (한국어 여성 음성)
GCP_TTS_VOICE_NAME=ko-KR-Standard-A
GCP_TTS_LANGUAGE_CODE=ko-KR
GCP_TTS_AUDIO_ENCODING=MP3
```

### 3. 사용 가능한 음성

**한국어 음성:**
- `ko-KR-Standard-A` - 여성 (기본값)
- `ko-KR-Standard-B` - 여성
- `ko-KR-Standard-C` - 남성
- `ko-KR-Standard-D` - 남성
- `ko-KR-Wavenet-A` - 여성 (Premium)
- `ko-KR-Wavenet-B` - 여성 (Premium)
- `ko-KR-Wavenet-C` - 남성 (Premium)
- `ko-KR-Wavenet-D` - 남성 (Premium)

**오디오 인코딩:**
- `MP3` - 가장 널리 사용되는 형식 (기본값)
- `LINEAR16` - WAV 형식
- `OGG_OPUS` - OGG 형식

## 🚀 API 사용

### 엔드포인트

`POST /api/tts`

### 요청

```json
{
  "text": "안녕하세요. AI 서포터입니다.",
  "voice_name": "ko-KR-Standard-A",  // 선택사항
  "language_code": "ko-KR",          // 선택사항
  "audio_encoding": "MP3"            // 선택사항
}
```

### 응답

```json
{
  "audio_content": "base64_encoded_audio_data...",
  "audio_encoding": "MP3",
  "mime_type": "audio/mpeg",
  "text_length": 15
}
```

### 사용 예시

**Python:**
```python
import requests
import base64

response = requests.post(
    "http://localhost:8000/api/tts",
    json={"text": "안녕하세요"}
)

result = response.json()
audio_data = base64.b64decode(result["audio_content"])

# 파일로 저장
with open("output.mp3", "wb") as f:
    f.write(audio_data)
```

**Android (Kotlin):**
```kotlin
// TTS 요청
val requestBody = JSONObject().apply {
    put("text", llmResponseText)
}

val response = httpClient.post("/api/tts") {
    contentType(ContentType.Application.Json)
    body = requestBody.toString()
}

val result = response.jsonObject
val audioBase64 = result.getString("audio_content")
val mimeType = result.getString("mime_type")

// Base64 디코딩
val audioBytes = Base64.decode(audioBase64, Base64.DEFAULT)

// 음성 재생
val mediaPlayer = MediaPlayer()
mediaPlayer.setDataSource(ByteArrayInputStream(audioBytes))
mediaPlayer.prepare()
mediaPlayer.start()
```

## 📝 제한사항

- **텍스트 길이**: 최대 5,000자 (GCP TTS 제한)
- **요청 제한**: GCP 할당량에 따라 제한될 수 있음

## 🐛 문제 해결

### GCP TTS 클라이언트 초기화 실패

1. 서비스 계정 키 파일 경로 확인
2. 환경 변수 `GOOGLE_APPLICATION_CREDENTIALS` 설정 확인
3. GCP 프로젝트에서 Cloud Text-to-Speech API 활성화 확인

### 음성 생성 실패

1. 텍스트 길이 확인 (5,000자 이하)
2. GCP 할당량 확인
3. 서비스 계정 권한 확인

## 🔗 관련 문서

- [GCP TTS 문서](https://cloud.google.com/text-to-speech/docs)
- [사용 가능한 음성 목록](https://cloud.google.com/text-to-speech/docs/voices)

