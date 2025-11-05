package com.onair.mobile.assistant.data.rag

import com.onair.mobile.assistant.core.model.dto.RagRequest
import com.onair.mobile.assistant.core.model.dto.RagResponse
import retrofit2.http.Body
import retrofit2.http.POST

/**
 * RAG Chat API 인터페이스
 * 
 * FastAPI 서버 엔드포인트: POST /rag/chat
 */
interface RagApiService {
    @POST("/rag/chat")
    suspend fun chat(@Body request: RagRequest): RagResponse
}

