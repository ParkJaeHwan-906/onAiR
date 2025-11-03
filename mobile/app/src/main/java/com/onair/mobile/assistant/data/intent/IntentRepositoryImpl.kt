package com.onair.mobile.assistant.data.intent

import android.content.Context
import com.onair.mobile.assistant.core.model.dto.IntentClassificationDto
import com.onair.mobile.assistant.domain.repository.IntentRepository

/**
 * Intent Repository 구현체
 */
class IntentRepositoryImpl(
    private val context: Context
) : IntentRepository {

    private val dataSource = OnnxIntentClassifierDataSource(context)

    init {
        dataSource.init()
    }

    override suspend fun classifyIntent(text: String): IntentClassificationDto {
        return dataSource.classify(text)
    }

    fun cleanup() {
        dataSource.cleanup()
    }
}

