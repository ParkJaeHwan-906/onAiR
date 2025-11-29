package com.onair.mobile.assistant.data.intent

import android.content.Context
import android.util.Log
import com.onair.mobile.assistant.core.model.dto.IntentClassificationDto
import com.onair.mobile.assistant.domain.repository.IntentRepository
import com.onair.mobile.assistant.domain.entity.IntentType

/**
 * Intent Repository 구현체
 * 
 * ⚠️ ONNX 모델 관련 코드 제거됨
 * Intent 분류는 이제 Gemini-Flash를 사용합니다 (서버 측에서 처리)
 * 모바일은 Socket.IO로부터 intent_result 이벤트를 받아서 사용합니다.
 */
class IntentRepositoryImpl() : IntentRepository {

    private val TAG = "IntentRepository"

    override suspend fun classifyIntent(text: String): IntentClassificationDto {
        // ⚠️ 이 메서드는 더 이상 사용되지 않습니다.
        // Intent 분류는 서버 측 Gemini-Flash에서 처리되며,
        // 모바일은 Socket.IO로부터 intent_result 이벤트를 받습니다.
        Log.w(TAG, "⚠️ classifyIntent()는 더 이상 사용되지 않습니다. 서버 측에서 Intent 분류를 수행합니다.")
        return IntentClassificationDto(
            intentType = IntentType.UNKNOWN,
            confidence = 0.0f,
            rawText = text
        )
    }
}
