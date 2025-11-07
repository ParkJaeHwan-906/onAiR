package com.onair.mobile.assistant.core.model.dto

/**
 * Socket.IO에서 수신하는 intent_result 이벤트 DTO
 * 버퍼링 STT 후 Gemini-Flash로 Intent 분류한 결과 수신
 */
data class IntentResultDto(
    val text: String,
    val intent: String,  // "OPERATOR" | "AI_SUPPORTER"
    val confidence: Double,  // 0.0~1.0
    val reasoning: String? = null,  // 판단 근거
    val stt_confidence: Double? = null  // STT 신뢰도
)

