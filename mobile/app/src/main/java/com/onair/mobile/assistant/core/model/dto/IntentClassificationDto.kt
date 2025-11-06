package com.onair.mobile.assistant.core.model.dto

import com.onair.mobile.assistant.domain.entity.IntentType

/**
 * Intent 분류 결과 DTO
 */
data class IntentClassificationDto(
    val intentType: IntentType,
    val confidence: Float,
    val rawText: String
)

