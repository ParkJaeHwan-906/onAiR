package com.onair.mobile.assistant.data.llm

import android.util.Log
import com.onair.mobile.assistant.core.model.dto.RagResponse
import com.onair.mobile.assistant.data.rag.RagRepositoryImpl
import com.onair.mobile.assistant.domain.repository.LlmRepository

/**
 * LLM Repository 구현체
 * 
 * RAG Chat API를 호출하여 질문 답변을 생성합니다.
 */
class LlmRepositoryImpl(
    private val ragRepository: RagRepositoryImpl
) : LlmRepository {
    
    private val TAG = "LlmRepository"
    
    override suspend fun generateRagResponse(query: String): RagResponse {
        return try {
            Log.d(TAG, "📡 RAG 응답 생성 요청: query=$query")
            val response = ragRepository.chat(query)
            Log.d(TAG, "✅ RAG 응답 생성 완료: answerable=${response.answerable}")
            response
        } catch (e: Exception) {
            Log.e(TAG, "❌ RAG 응답 생성 실패: ${e.message}")
            throw e
        }
    }
}

