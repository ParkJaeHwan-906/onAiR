package com.onair.mobile.assistant.domain.repository

import com.onair.mobile.assistant.core.model.dto.RagResponse

/**
 * RAG 기반 LLM API를 호출하는 Repository 인터페이스
 * 
 * FastAPI 서버로 요청 전송 (서버에서 EC2로 전달)
 */
interface LlmRepository {
    /**
     * RAG Chat API 호출
     * 
     * @param query 사용자 질문
     * @return RAG 응답
     */
    suspend fun generateRagResponse(query: String): RagResponse
}
