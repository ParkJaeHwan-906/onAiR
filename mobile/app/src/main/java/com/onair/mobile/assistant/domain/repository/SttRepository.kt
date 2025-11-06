package com.onair.mobile.assistant.domain.repository

/**
 * Speech-to-Text 리포지토리 인터페이스
 */
interface SttRepository {
    
    /**
     * 오디오 바이트를 텍스트로 변환
     * @param audioBytes 오디오 파일의 바이트 배열
     * @return 인식된 텍스트, 실패 시 null
     */
    suspend fun transcribe(audioBytes: ByteArray): com.onair.mobile.assistant.core.common.Result<String>
}

