package com.onair.mobile.assistant.domain.repository

/**
 * RAG 기반 LLM API를 호출하는 Repository 인터페이스
 * 
 * FastAPI 서버로 요청 전송 (서버에서 EC2로 전달)
 * TODO: 실제 API 연동 구현 필요
 */
interface LlmRepository {
    // TODO: RAG+LLM API 호출 구현
    // suspend fun generateRagResponse(query: String): LlmResponse
}

