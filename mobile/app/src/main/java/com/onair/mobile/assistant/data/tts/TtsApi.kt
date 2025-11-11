package com.onair.mobile.assistant.data.tts

import retrofit2.http.Body
import retrofit2.http.POST

/**
 * TTS API 인터페이스
 */
interface TtsApi {
    @POST("/api/tts")
    suspend fun generateSpeech(@Body request: TtsRequest): TtsResponse
}

data class TtsRequest(
    val text: String,
    val voice_name: String? = null,
    val language_code: String? = null,
    val audio_encoding: String? = null
)

data class TtsResponse(
    val audio_content: String,  // Base64 인코딩된 오디오 데이터
    val audio_encoding: String,
    val mime_type: String,
    val text_length: Int
)

