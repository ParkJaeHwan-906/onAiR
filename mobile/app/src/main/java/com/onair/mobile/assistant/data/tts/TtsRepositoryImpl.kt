package com.onair.mobile.assistant.data.tts

import android.util.Log
import com.onair.mobile.assistant.domain.repository.TtsRepository
import com.onair.mobile.communicate.data.network.ApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * TTS Repository 구현체
 * 
 * FastAPI 서버에서 받은 Base64 인코딩된 오디오를 재생하거나,
 * 텍스트를 TTS API로 변환하여 재생합니다.
 */
class TtsRepositoryImpl(
    private val mediaPlayerController: MediaPlayerController,
) : TtsRepository {
    
    private val TAG = "TtsRepository"
    private val ttsApi: TtsApi by lazy {
        ApiClient.fastApiRetrofit.create(TtsApi::class.java)
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
    
    override suspend fun speakText(text: String, voiceName: String?, languageCode: String?, onCompletion: (() -> Unit)?) {
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
                
                // 오디오 재생 (완료 콜백 포함)
                playAudio(response.audio_content, response.mime_type, onCompletion)
            } catch (e: Exception) {
                Log.e(TAG, "❌ TTS 생성 실패: ${e.message}")
                e.printStackTrace()
                onCompletion?.invoke()  // 오류 발생 시에도 콜백 호출
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

