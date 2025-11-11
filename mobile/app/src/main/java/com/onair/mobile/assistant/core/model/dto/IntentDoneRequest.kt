package com.onair.mobile.assistant.core.model.dto

/**
 * Intent 분기 완료 알림 요청 DTO
 */
data class IntentDoneRequest(
    val branch: String  // "AI_SUPPORTER" or "OPERATOR"
)

