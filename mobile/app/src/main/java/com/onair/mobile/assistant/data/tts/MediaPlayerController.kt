package com.onair.mobile.assistant.data.tts

import android.content.Context
import android.media.MediaPlayer
import android.util.Base64
import android.util.Log
import java.io.File

/**
 * MediaPlayer를 사용한 오디오 재생 컨트롤러
 * 
 * Base64 인코딩된 오디오 데이터를 디코딩하여 재생합니다.
 */
class MediaPlayerController(private val context: Context) {
    private val TAG = "MediaPlayerController"
    private var mediaPlayer: MediaPlayer? = null
    
    /**
     * Base64 인코딩된 오디오 재생
     * 
     * @param base64Audio Base64 인코딩된 오디오 데이터
     * @param mimeType MIME 타입 (예: "audio/mpeg", "audio/wav")
     */
    suspend fun playBase64Audio(base64Audio: String, mimeType: String?) {
        try {
            // Base64 디코딩
            val audioBytes = Base64.decode(base64Audio, Base64.DEFAULT)
            
            // 파일 확장자 결정
            val extension = when (mimeType) {
                "audio/mpeg" -> "mp3"
                "audio/wav", "audio/wave" -> "wav"
                "audio/ogg" -> "ogg"
                else -> "mp3"  // 기본값
            }
            
            // 임시 파일 생성
            val tempFile = File(context.cacheDir, "temp_audio_${System.currentTimeMillis()}.$extension")
            tempFile.writeBytes(audioBytes)
            
            Log.d(TAG, "📁 임시 오디오 파일 생성: ${tempFile.absolutePath}")
            
            // 기존 MediaPlayer 정리
            mediaPlayer?.release()
            
            // MediaPlayer로 재생
            mediaPlayer = MediaPlayer().apply {
                setDataSource(tempFile.absolutePath)
                prepare()
                setOnCompletionListener {
                    release()
                    mediaPlayer = null
                    // 재생 후 임시 파일 삭제
                    if (tempFile.exists()) {
                        tempFile.delete()
                        Log.d(TAG, "🗑️ 임시 오디오 파일 삭제")
                    }
                }
                setOnErrorListener { _, what, extra ->
                    Log.e(TAG, "❌ MediaPlayer 오류: what=$what, extra=$extra")
                    release()
                    mediaPlayer = null
                    false
                }
                start()
                Log.i(TAG, "▶️ 오디오 재생 시작")
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ 오디오 재생 실패: ${e.message}")
            e.printStackTrace()
        }
    }
    
    /**
     * 오디오 재생 중지
     */
    fun stop() {
        try {
            mediaPlayer?.release()
            mediaPlayer = null
            Log.i(TAG, "⏹️ 오디오 재생 중지")
        } catch (e: Exception) {
            Log.e(TAG, "❌ 오디오 중지 실패: ${e.message}")
        }
    }
    
    /**
     * MediaPlayer 리소스 정리
     */
    fun cleanup() {
        stop()
    }
}

