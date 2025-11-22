package com.onair.mobile.assistant.core.model.dto

/**
 * RAG Chat API 응답 DTO
 */
data class RagResponse(
    val answerable: Boolean,
    val reason: String? = null,
    val generator_model: String? = null,
    val result: RagResult? = null,
    val rag_stats: RagStats? = null,
    val source_sections: List<Any>? = null,
    val debug: RagDebug? = null
)

/**
 * RAG 결과 (answerable=true일 때)
 */
data class RagResult(
    val query: String,
    val clarifier_model: String? = null,
    val generator_model: String? = null,
    val answer: String,
    val audio_content: String? = null,  // Base64 인코딩된 오디오
    val audio_encoding: String? = null,
    val mime_type: String? = null,
    val borderline: Boolean? = null,
    val followup_prompt: String? = null,
    val rag_stats: RagStats? = null,
    val source_sections: List<Any>? = null,
    val citations: List<Citation>? = null
)

/**
 * RAG 통계
 */
data class RagStats(
    val retrieval_strength: Float? = null,
    val evidence_sufficiency: Float? = null
)

/**
 * 인용 정보
 */
data class Citation(
    val section: String? = null,
    val pages: String? = null
)

/**
 * 디버그 정보
 */
data class RagDebug(
    val gate_decision: String? = null,
    val gate_rule: String? = null,
    val failed_clauses: List<String>? = null,
    val hits: Int? = null
)

