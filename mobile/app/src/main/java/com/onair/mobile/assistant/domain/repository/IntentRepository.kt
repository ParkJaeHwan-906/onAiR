package com.onair.mobile.assistant.domain.repository

import com.onair.mobile.assistant.core.model.dto.IntentClassificationDto

/**
 * Intent 분류 Repository 인터페이스
 */
interface IntentRepository {
    suspend fun classifyIntent(text: String): IntentClassificationDto
}

