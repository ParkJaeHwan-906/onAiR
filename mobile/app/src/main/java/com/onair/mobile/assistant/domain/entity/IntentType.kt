package com.onair.mobile.assistant.domain.entity

/**
 * Intent 분류 결과 타입
 * 
 * AI 서포터 서비스에서는 무조건 두 가지 중 하나로 분류됩니다:
 * - OPERATOR: 운영자 연결 (RTC Start)
 * - AI_SUPPORTER: AI 서포터 모드 (Vision Analyzer → Clarification → RAG + LLM)
 */
enum class IntentType(val value: String) {
    OPERATOR("operator"),           // 운영자 연결
    AI_SUPPORTER("ai_supporter"),   // AI 서포터 모드
    UNKNOWN("unknown")              // 알 수 없음 (에러 케이스)
}

