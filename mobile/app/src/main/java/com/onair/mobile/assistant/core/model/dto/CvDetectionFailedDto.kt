package com.onair.mobile.assistant.core.model.dto

/**
 * CV 모델 오류 탐지 실패 이벤트 DTO
 * FastAPI 서버에서 CV 모델이 오류를 탐지하지 못했을 때 전송
 */
data class CvDetectionFailedDto(
    val message: String = "오류를 탐지하지 못했습니다. AI_SUPPORTER와의 대화를 통해 문제를 해결하겠습니다."
)

/**
 * Clarify 질문/답변 턴 DTO (작업자 질문 + LLM 답변)
 * Streaming STT 세션 중 Clarify 루프에서 사용
 */
data class ClarifyQaTurnDto(
    val session_id: String,
    val turn_id: Int,
    val user_question: String,  // 작업자 질문 (STT 결과)
    val llm_answer: String,  // LLM 답변 (텍스트)
    val audio_content: String? = null,  // TTS 음성 파일 (base64)
    val audio_encoding: String? = null,  // TTS 음성 인코딩 (예: "audio/mpeg")
    val need_clarify: Boolean = true,  // 추가 구체화 필요 여부
    val gate_decision: String? = null,  // "RED" | "YELLOW" | "GREEN"
    val status: String = "success"  // "success" | "error"
)

