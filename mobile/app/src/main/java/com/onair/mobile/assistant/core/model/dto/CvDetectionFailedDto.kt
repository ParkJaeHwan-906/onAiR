package com.onair.mobile.assistant.core.model.dto

/**
 * CV 모델 오류 탐지 실패 이벤트 DTO
 * FastAPI 서버에서 CV 모델이 오류를 탐지하지 못했을 때 전송
 */
data class CvDetectionFailedDto(
    val message: String = "오류를 탐지하지 못했습니다. AI_SUPPORTER와의 대화를 통해 문제를 해결하겠습니다."
)

/**
 * CV 모델 정상 탐지 이벤트 DTO
 * FastAPI 서버에서 CV 모델이 정상 상태를 탐지했을 때 전송
 */
data class CvDetectionNormalDto(
    val message: String = "탐지 결과 정상입니다. 오퍼레이터와의 통신을 통해 문제를 해결하겠습니다."
)

/**
 * CV 모델 이상 탐지 이벤트 DTO
 * FastAPI 서버에서 CV 모델이 이상을 탐지했을 때 전송 (1단계: 간단한 알림)
 */
data class CvDetectionAnomalyDto(
    val message: String,  // 간단한 탐지 알림 메시지
    val audio_content: String? = null,  // TTS 음성 파일 (base64)
    val audio_encoding: String? = null,  // TTS 음성 인코딩 (예: "audio/mpeg")
    val cv_detection_result: CvDetectionResultDto? = null
)

/**
 * CV 탐지 결과 DTO
 */
data class CvDetectionResultDto(
    val device_type: String,
    val modules: List<Any>? = null,
    val anomalies: Map<String, Any>? = null,
    val message: String? = null
)


