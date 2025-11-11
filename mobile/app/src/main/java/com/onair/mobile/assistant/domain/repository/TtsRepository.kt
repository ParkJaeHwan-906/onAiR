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
     * 텍스트를 TTS로 변환하여 재생
     * 
     * @param text TTS로 변환할 텍스트
     * @param voiceName 음성 이름 (선택사항)
     * @param languageCode 언어 코드 (선택사항, 기본값: "ko-KR")
     */
    suspend fun speakText(text: String, voiceName: String? = null, languageCode: String? = "ko-KR")
    
    /**
     * 오디오 재생 중지
     */
    fun stop()
}

