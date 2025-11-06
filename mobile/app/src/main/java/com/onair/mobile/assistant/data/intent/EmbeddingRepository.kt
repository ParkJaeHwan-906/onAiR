package com.onair.mobile.assistant.data.intent

import android.util.Log
import com.onair.mobile.assistant.core.model.dto.EmbeddingRequest
import com.onair.mobile.assistant.core.model.dto.EmbeddingResponse
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

/**
 * Phi-3 임베딩 추출 Repository 구현체
 * 
 * FastAPI 서버로부터 Phi-3 임베딩을 받아옵니다.
 */
class EmbeddingRepository(
    private val baseUrl: String  // 예: "http://192.168.0.100:8000"
) {
    private val TAG = "EmbeddingRepository"
    
    private val api: EmbeddingApi by lazy {
        // Retrofit의 baseUrl은 반드시 끝에 슬래시(/)가 있어야 함
        val normalizedBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        
        Retrofit.Builder()
            .baseUrl(normalizedBaseUrl)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(EmbeddingApi::class.java)
    }
    
    /**
     * 텍스트를 Phi-3 임베딩으로 변환
     * 
     * @param text 입력 텍스트
     * @return 3072차원 FloatArray (Phi-3 임베딩)
     */
    suspend fun extractEmbedding(text: String): FloatArray {
        return try {
            Log.d(TAG, "📡 FastAPI 서버에 임베딩 요청: $text")
            
            val request = EmbeddingRequest(text = text)
            val response: EmbeddingResponse = api.extractEmbedding(request)
            
            val embedding = response.embedding.toFloatArray()
            
            Log.d(TAG, "✅ 임베딩 수신 완료: ${embedding.size}차원")
            
            if (embedding.size != 3072) {
                Log.w(TAG, "⚠️ 임베딩 차원 불일치: 예상 3072, 실제 ${embedding.size}")
            }
            
            embedding
        } catch (e: Exception) {
            Log.e(TAG, "❌ 임베딩 추출 실패: ${e.message}")
            e.printStackTrace()
            throw IllegalStateException("Phi-3 임베딩 추출 실패: ${e.message}", e)
        }
    }
}

