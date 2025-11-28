package com.onair.mobile.assistant.data.rag

import android.util.Log
import com.onair.mobile.assistant.core.model.dto.RagRequest
import com.onair.mobile.assistant.core.model.dto.RagResponse
import com.onair.mobile.communicate.data.network.ApiClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

/**
 * RAG Chat Repository 구현체
 * 
 * FastAPI 서버의 /rag/chat 엔드포인트 호출
 */
class RagRepositoryImpl() {
    private val TAG = "RagRepository"
    
    private val api: RagApiService by lazy {
        ApiClient.fastApiRetrofit.create(RagApiService::class.java)
    }
    
    /**
     * RAG Chat API 호출
     * 
     * @param query 사용자 질문
     * @return RAG 응답
     */
    suspend fun chat(query: String): RagResponse {
        return try {
            Log.d(TAG, "📡 RAG Chat API 호출: query=$query")
            
            val request = RagRequest(query = query)
            val response = api.chat(request)
            
            Log.d(TAG, "✅ RAG 응답 수신: answerable=${response.answerable}")
            
            response
        } catch (e: Exception) {
            Log.e(TAG, "❌ RAG Chat API 호출 실패: ${e.message}")
            e.printStackTrace()
            throw IllegalStateException("RAG Chat API 호출 실패: ${e.message}", e)
        }
    }
}

