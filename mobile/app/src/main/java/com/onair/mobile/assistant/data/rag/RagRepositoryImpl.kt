package com.onair.mobile.assistant.data.rag

import android.util.Log
import com.onair.mobile.assistant.core.model.dto.RagRequest
import com.onair.mobile.assistant.core.model.dto.RagResponse
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

/**
 * RAG Chat Repository 구현체
 * 
 * FastAPI 서버의 /rag/chat 엔드포인트 호출
 */
class RagRepositoryImpl(
    private val baseUrl: String  // 예: "http://192.168.0.100:8000"
) {
    private val TAG = "RagRepository"
    
    private val api: RagApiService by lazy {
        // Retrofit의 baseUrl은 반드시 끝에 슬래시(/)가 있어야 함
        val normalizedBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        
        Retrofit.Builder()
            .baseUrl(normalizedBaseUrl)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(RagApiService::class.java)
    }
    
    /**
     * RAG Chat API 호출
     * 
     * @param query 사용자 질문
     * @param sessionId 세션 ID (Clarify 루프 동안 동일 ID 유지)
     * @return RAG 응답
     */
    suspend fun chat(query: String, sessionId: String?): RagResponse {
        return try {
            Log.d(TAG, "📡 RAG Chat API 호출: query=$query, sessionId=$sessionId")
            
            val request = RagRequest(query = query, session_id = sessionId)
            val response = api.chat(request)
            
            Log.d(TAG, "✅ RAG 응답 수신: answerable=${response.answerable}, need_clarify=${response.need_clarify}")
            
            response
        } catch (e: Exception) {
            Log.e(TAG, "❌ RAG Chat API 호출 실패: ${e.message}")
            e.printStackTrace()
            throw IllegalStateException("RAG Chat API 호출 실패: ${e.message}", e)
        }
    }
}

