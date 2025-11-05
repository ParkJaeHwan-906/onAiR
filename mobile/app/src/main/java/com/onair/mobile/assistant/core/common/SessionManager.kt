package com.onair.mobile.assistant.core.common

import java.util.UUID

/**
 * 세션 관리 클래스
 * 
 * 역할:
 * - 세션 ID 생성 및 관리
 * - Clarify 루프 동안 동일 세션 ID 유지
 * - 최종 답변 후 세션 초기화
 */
class SessionManager {
    private var currentSessionId: String? = null
    
    /**
     * 세션 ID를 가져오거나 새로 생성
     * 
     * @return 현재 세션 ID (없으면 새로 생성)
     */
    fun getOrCreateSessionId(): String {
        if (currentSessionId == null) {
            currentSessionId = UUID.randomUUID().toString()
        }
        return currentSessionId!!
    }
    
    /**
     * 현재 세션 ID 조회
     * 
     * @return 현재 세션 ID (없으면 null)
     */
    fun getCurrentSessionId(): String? = currentSessionId
    
    /**
     * 세션 초기화
     * 최종 답변 수신 후 호출하여 다음 질문을 새 세션으로 시작
     */
    fun resetSession() {
        currentSessionId = null
    }
    
    /**
     * 세션이 활성 상태인지 확인
     * 
     * @return 세션이 있으면 true
     */
    fun hasActiveSession(): Boolean = currentSessionId != null
}

