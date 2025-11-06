package com.onair.mobile.assistant.core.model.dto

/**
 * 임베딩 추출 요청 DTO
 */
data class EmbeddingRequest(
    val text: String
)

/**
 * 임베딩 추출 응답 DTO
 * 
 * FastAPI 서버로부터 받는 응답:
 * {
 *   "embedding": [0.123, -0.456, 0.789, ...]  // 3072차원 FloatArray
 * }
 */
data class EmbeddingResponse(
    val embedding: List<Float>  // 3072차원
)

