package com.onair.mobile.assistant.core.model.dto

/**
 * RAG Chat API 요청 DTO
 * 
 * FastAPI 서버 엔드포인트: POST /rag/chat
 */
data class RagRequest(
    val query: String,
    val session_id: String? = null
)

