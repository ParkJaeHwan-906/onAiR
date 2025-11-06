package com.onair.mobile.assistant.domain.repository

/**
 * TTS Repository 인터페이스
 */
interface TtsRepository {
    /**
     * Base64 인코딩된 오디오 재생
     * 
     * @param base64Audio Base64 인코딩된 오디오 데이터
     * @param mimeType MIME 타입 (예: "audio/mpeg")
     */
    suspend fun playAudio(base64Audio: String, mimeType: String?)
    
    /**
     * 오디오 재생 중지
     */
    fun stop()
}

