package com.onair.mobile.assistant.core.model.dto

/**
 * STT 모드 설정 요청 DTO
 */
data class SttModeRequest(
    val mode: String  // "buffered" or "streaming"
)

