package com.onair.mobile.assistant.core.model.dto

/**
 * Socket.IO에서 수신하는 final_answer 이벤트 DTO
 * 최종 답변 수신
 */
data class FinalAnswerDto(
    val session_id: String,
    val turn_id: Int,
    val status: String,  // "completed"
    val answer: String,
    val audio_content: String? = null,  // Base64 인코딩된 오디오
    val audio_encoding: String? = null,
    val citations: List<Citation>? = null
)

