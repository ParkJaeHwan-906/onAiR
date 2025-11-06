package com.onair.mobile.assistant.data.tts

import android.content.Context
import android.util.Log
import com.onair.mobile.assistant.domain.repository.TtsRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * TTS Repository 구현체
 * 
 * FastAPI 서버에서 받은 Base64 인코딩된 오디오를 재생합니다.
 */
class TtsRepositoryImpl(
    private val context: Context,
    private val mediaPlayerController: MediaPlayerController
) : TtsRepository {
    
    private val TAG = "TtsRepository"
    
    override suspend fun playAudio(base64Audio: String, mimeType: String?) {
        withContext(Dispatchers.IO) {
            try {
                Log.d(TAG, "🎵 오디오 재생 시작: mimeType=$mimeType")
                mediaPlayerController.playBase64Audio(base64Audio, mimeType)
            } catch (e: Exception) {
                Log.e(TAG, "❌ 오디오 재생 실패: ${e.message}")
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

