package com.onair.mobile.assistant.data.intent

import retrofit2.http.Body
import retrofit2.http.POST

/**
 * Phi-3 임베딩 추출 API 인터페이스
 * 
 * FastAPI 서버 엔드포인트: POST /api/embedding
 */
interface EmbeddingApi {
    @POST("/api/embedding")
    suspend fun extractEmbedding(
        @Body request: com.onair.mobile.assistant.core.model.dto.EmbeddingRequest
    ): com.onair.mobile.assistant.core.model.dto.EmbeddingResponse
}

