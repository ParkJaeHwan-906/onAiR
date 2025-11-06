package com.onair.mobile.assistant.core.model.dto

/**
 * Socket.IO에서 수신하는 embedding_result 이벤트 DTO
 * 버퍼링 STT 후 Phi-3 임베딩 수신 (Intent 분류용)
 */
data class EmbeddingResultDto(
    val text: String,
    val embedding: List<Float>,  // 3072차원
    val dimension: Int,
    val confidence: Double? = null
)

