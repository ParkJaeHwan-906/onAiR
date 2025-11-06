package com.onair.mobile.assistant.core.model.dto

/**
 * Socket.IO에서 수신하는 clarify_turn 이벤트 DTO
 * Clarify 질문/답변 턴 수신
 */
data class ClarifyTurnDto(
    val session_id: String,
    val turn_id: Int,
    val status: String,  // "clarify" | "error"
    val gate_decision: String? = null,  // "RED" | "YELLOW" | "GREEN"
    val question: String? = null,
    val examples: List<String>? = null,
    val evidence_trace: Map<String, Any>? = null,
    val missing_info: List<String>? = null,
    val message: String? = null  // 에러 메시지 (status="error"일 때)
)

