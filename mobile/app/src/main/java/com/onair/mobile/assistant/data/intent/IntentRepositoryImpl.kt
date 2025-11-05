package com.onair.mobile.assistant.data.intent

import android.content.Context
import android.util.Log
import com.onair.mobile.assistant.core.model.dto.IntentClassificationDto
import com.onair.mobile.assistant.domain.repository.IntentRepository

/**
 * Intent Repository 구현체
 * 
 * FastAPI 서버로부터 Phi-3 임베딩을 받아서
 * intent_classifier.int8.onnx 모델로 Intent 분류를 수행합니다.
 */
class IntentRepositoryImpl(
    private val context: Context,
    private val embeddingRepository: EmbeddingRepository? = null  // FastAPI 서버 URL 주입 필요
) : IntentRepository {

    private val TAG = "IntentRepository"
    private val dataSource = OnnxIntentClassifierDataSource(context)

    init {
        dataSource.init()
    }

    override suspend fun classifyIntent(text: String): IntentClassificationDto {
        return try {
            // 1. FastAPI 서버로부터 Phi-3 임베딩 추출
            val embedding = if (embeddingRepository != null) {
                Log.d(TAG, "📡 FastAPI 서버로부터 Phi-3 임베딩 추출 중...")
                embeddingRepository.extractEmbedding(text)
            } else {
                Log.w(TAG, "⚠️ EmbeddingRepository가 주입되지 않음 - 임시 분류 사용")
                // 임시: 해시 기반 임베딩 사용 (개발/테스트용)
                return dataSource.classify(text)
            }
            
            // 2. ONNX 모델로 Intent 분류
            Log.d(TAG, "🧠 ONNX 모델로 Intent 분류 중...")
            dataSource.classifyWithEmbedding(embedding, text)
            
        } catch (e: Exception) {
            Log.e(TAG, "❌ Intent 분류 실패: ${e.message}")
            e.printStackTrace()
            IntentClassificationDto(
                intentType = com.onair.mobile.assistant.domain.entity.IntentType.UNKNOWN,
                confidence = 0.0f,
                rawText = text
            )
        }
    }

    /**
     * 임베딩을 직접 받아서 Intent 분류 수행
     * Socket.IO로부터 embedding_result 이벤트 수신 시 사용
     */
    suspend fun classifyWithEmbedding(embedding: FloatArray, text: String): IntentClassificationDto {
        return try {
            Log.d(TAG, "🧠 ONNX 모델로 Intent 분류 중 (임베딩 직접 사용)...")
            dataSource.classifyWithEmbedding(embedding, text)
        } catch (e: Exception) {
            Log.e(TAG, "❌ Intent 분류 실패: ${e.message}")
            e.printStackTrace()
            IntentClassificationDto(
                intentType = com.onair.mobile.assistant.domain.entity.IntentType.UNKNOWN,
                confidence = 0.0f,
                rawText = text
            )
        }
    }

    fun cleanup() {
        dataSource.cleanup()
    }
}

