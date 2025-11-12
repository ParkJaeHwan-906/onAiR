package com.onair.mobile.assistant.data.tts

import android.content.Context
import android.util.Log
import com.onair.mobile.assistant.domain.repository.TtsRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

/**
 * TTS Repository 구현체
 * 
 * FastAPI 서버에서 받은 Base64 인코딩된 오디오를 재생하거나,
 * 텍스트를 TTS API로 변환하여 재생합니다.
 */
class TtsRepositoryImpl(
    private val context: Context,
    private val mediaPlayerController: MediaPlayerController,
    private val baseUrl: String  // FastAPI 서버 URL
) : TtsRepository {
    
    private val TAG = "TtsRepository"
    private val ttsApi: TtsApi by lazy {
        // Retrofit의 baseUrl은 반드시 끝에 슬래시(/)가 있어야 함
        val retrofitBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        Retrofit.Builder()
            .baseUrl(retrofitBaseUrl)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(TtsApi::class.java)
    }
    
    override suspend fun playAudio(base64Audio: String, mimeType: String?, onCompletion: (() -> Unit)?) {
        withContext(Dispatchers.IO) {
            try {
                Log.d(TAG, "🎵 오디오 재생 시작: mimeType=$mimeType")
                mediaPlayerController.playBase64Audio(base64Audio, mimeType, onCompletion)
            } catch (e: Exception) {
                Log.e(TAG, "❌ 오디오 재생 실패: ${e.message}")
                e.printStackTrace()
                onCompletion?.invoke()  // 오류 발생 시에도 콜백 호출
            }
        }
    }
    
    override suspend fun speakText(text: String, voiceName: String?, languageCode: String?) {
        withContext(Dispatchers.IO) {
            try {
                Log.d(TAG, "🗣️ TTS 요청: text=$text")
                
                val request = TtsRequest(
                    text = text,
                    voice_name = voiceName,
                    language_code = languageCode
                )
                
                val response = ttsApi.generateSpeech(request)
                
                Log.d(TAG, "✅ TTS 응답 수신: mimeType=${response.mime_type}, length=${response.text_length}")
                
                // 오디오 재생
                playAudio(response.audio_content, response.mime_type)
            } catch (e: Exception) {
                Log.e(TAG, "❌ TTS 생성 실패: ${e.message}")
                e.printStackTrace()
            }
        }
    }
    
    override fun stop() {
        mediaPlayerController.stop()
    }
    
    /**
     * 리소스 정리
     */
    fun cleanup() {
        mediaPlayerController.cleanup()
    }
}

