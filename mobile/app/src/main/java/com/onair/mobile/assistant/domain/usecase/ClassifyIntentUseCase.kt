package com.onair.mobile.assistant.domain.usecase

import com.onair.mobile.assistant.core.model.dto.IntentClassificationDto
import com.onair.mobile.assistant.domain.repository.IntentRepository

/**
 * Intent 분류 UseCase
 */
class ClassifyIntentUseCase(
    private val intentRepository: IntentRepository
) {
    suspend operator fun invoke(text: String): IntentClassificationDto {
        return intentRepository.classifyIntent(text)
    }
}

