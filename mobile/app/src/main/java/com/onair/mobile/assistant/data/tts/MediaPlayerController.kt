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
     * @param onCompletion 재생 완료 콜백
     */
    suspend fun playBase64Audio(base64Audio: String, mimeType: String?, onCompletion: (() -> Unit)? = null) {
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
            mediaPlayer = null
            
            // 파일 존재 여부 확인
            if (!tempFile.exists() || tempFile.length() == 0L) {
                Log.e(TAG, "❌ 임시 파일이 생성되지 않았거나 비어있습니다: ${tempFile.absolutePath}")
                onCompletion?.invoke()
                return
            }
            
            // MediaPlayer 생성 및 설정
            val player = MediaPlayer()
            val finalTempFile = tempFile  // 람다에서 사용하기 위해 로컬 변수로 복사
            
            try {
                player.setDataSource(finalTempFile.absolutePath)
                Log.d(TAG, "📂 MediaPlayer 데이터 소스 설정 완료: ${finalTempFile.absolutePath}")
                
                // prepare() 호출 - IOException을 던질 수 있음
                player.prepare()
                Log.d(TAG, "✅ MediaPlayer prepare() 완료")
                
                // 리스너 설정
                player.setOnCompletionListener {
                    Log.i(TAG, "✅ 오디오 재생 완료")
                    player.release()
                    mediaPlayer = null
                    // 재생 후 임시 파일 삭제
                    if (finalTempFile.exists()) {
                        finalTempFile.delete()
                        Log.d(TAG, "🗑️ 임시 오디오 파일 삭제")
                    }
                    // 재생 완료 콜백 호출
                    onCompletion?.invoke()
                }
                
                player.setOnErrorListener { _, what, extra ->
                    Log.e(TAG, "❌ MediaPlayer 오류: what=$what, extra=$extra")
                    player.release()
                    mediaPlayer = null
                    // 재생 후 임시 파일 삭제
                    if (finalTempFile.exists()) {
                        finalTempFile.delete()
                        Log.d(TAG, "🗑️ 임시 오디오 파일 삭제 (오류 발생)")
                    }
                    onCompletion?.invoke()  // 오류 발생 시에도 콜백 호출
                    false
                }
                
                // 재생 시작
                player.start()
                mediaPlayer = player
                Log.i(TAG, "▶️ 오디오 재생 시작")
                
            } catch (e: java.io.IOException) {
                Log.e(TAG, "❌ MediaPlayer prepare() 실패: ${e.message}")
                e.printStackTrace()
                player.release()
                mediaPlayer = null
                // 임시 파일 삭제
                if (finalTempFile.exists()) {
                    finalTempFile.delete()
                }
                onCompletion?.invoke()
            } catch (e: Exception) {
                Log.e(TAG, "❌ MediaPlayer 설정 실패: ${e.message}")
                e.printStackTrace()
                player.release()
                mediaPlayer = null
                // 임시 파일 삭제
                if (finalTempFile.exists()) {
                    finalTempFile.delete()
                }
                onCompletion?.invoke()
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ 오디오 재생 실패: ${e.message}")
            e.printStackTrace()
            onCompletion?.invoke()  // 오류 발생 시에도 콜백 호출
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
     * 로컬 음성 파일 재생 (assets 또는 raw 폴더)
     * 
     * @param fileName 파일명 (예: "001_onAir_서비스를_시작합니다_어떤_것을_도와드릴까요.mp3")
     * @param onCompletion 재생 완료 콜백
     */
    suspend fun playLocalAudio(fileName: String, onCompletion: (() -> Unit)? = null) {
        var tempFile: File? = null
        try {
            Log.i(TAG, "🎵 로컬 오디오 재생 시작: $fileName")
            
            // assets 폴더에서 파일 목록 확인 (디버깅용)
            try {
                val assetManager = context.assets
                val assetFiles = assetManager.list("")
                Log.d(TAG, "📂 Assets 폴더 파일 목록: ${assetFiles?.joinToString(", ") ?: "없음"}")
                
                // 요청한 파일이 assets에 있는지 확인
                val fileExists = assetFiles?.contains(fileName) == true
                if (!fileExists) {
                    Log.e(TAG, "❌ Assets 폴더에 파일이 없습니다: $fileName")
                    Log.e(TAG, "   사용 가능한 파일: ${assetFiles?.joinToString(", ") ?: "없음"}")
                    onCompletion?.invoke()
                    return
                }
                Log.d(TAG, "✅ Assets 폴더에서 파일 확인: $fileName")
            } catch (e: Exception) {
                Log.e(TAG, "❌ Assets 폴더 목록 조회 실패: ${e.message}")
            }
            
            // assets 폴더에서 파일 읽기
            val assetManager = context.assets
            Log.d(TAG, "📖 Assets 파일 열기 시도: $fileName")
            val inputStream = try {
                assetManager.open(fileName)
            } catch (e: java.io.FileNotFoundException) {
                Log.e(TAG, "❌ Assets 파일을 찾을 수 없습니다: $fileName")
                Log.e(TAG, "   오류: ${e.message}")
                e.printStackTrace()
                onCompletion?.invoke()
                return
            }
            
            Log.d(TAG, "✅ Assets 파일 열기 성공: $fileName")
            
            // 임시 파일 생성
            tempFile = File(context.cacheDir, "temp_local_audio_${System.currentTimeMillis()}.mp3")
            Log.d(TAG, "📝 임시 파일 생성 시작: ${tempFile.absolutePath}")
            
            var bytesCopied = 0L
            tempFile.outputStream().use { output ->
                bytesCopied = inputStream.copyTo(output)
            }
            inputStream.close()
            
            Log.i(TAG, "📁 로컬 오디오 파일 복사 완료: ${tempFile.absolutePath}")
            Log.d(TAG, "   복사된 크기: ${bytesCopied} bytes (${bytesCopied / 1024} KB)")
            
            // 파일 존재 여부 확인
            if (!tempFile.exists()) {
                Log.e(TAG, "❌ 임시 파일이 생성되지 않았습니다: ${tempFile.absolutePath}")
                onCompletion?.invoke()
                return
            }
            
            val fileSize = tempFile.length()
            if (fileSize == 0L) {
                Log.e(TAG, "❌ 임시 파일이 비어있습니다: ${tempFile.absolutePath} (크기: $fileSize bytes)")
                onCompletion?.invoke()
                return
            }
            
            Log.d(TAG, "✅ 임시 파일 확인 완료: 크기=${fileSize} bytes (${fileSize / 1024} KB)")
            
            // 기존 MediaPlayer 정리
            mediaPlayer?.release()
            mediaPlayer = null
            
            // MediaPlayer 생성 및 설정
            val player = MediaPlayer()
            val finalTempFile = tempFile  // 람다에서 사용하기 위해 로컬 변수로 복사
            
            try {
                player.setDataSource(finalTempFile.absolutePath)
                Log.d(TAG, "📂 MediaPlayer 데이터 소스 설정 완료: ${finalTempFile.absolutePath}")
                
                // prepare() 호출 - IOException을 던질 수 있음
                player.prepare()
                Log.d(TAG, "✅ MediaPlayer prepare() 완료")
                
                // 리스너 설정
                player.setOnCompletionListener {
                    Log.i(TAG, "✅ 로컬 오디오 재생 완료: $fileName")
                    player.release()
                    mediaPlayer = null
                    // 재생 후 임시 파일 삭제
                    if (finalTempFile.exists()) {
                        finalTempFile.delete()
                        Log.d(TAG, "🗑️ 임시 오디오 파일 삭제")
                    }
                    // 재생 완료 콜백 호출
                    onCompletion?.invoke()
                }
                
                player.setOnErrorListener { _, what, extra ->
                    Log.e(TAG, "❌ MediaPlayer 오류: what=$what, extra=$extra")
                    player.release()
                    mediaPlayer = null
                    // 재생 후 임시 파일 삭제
                    if (finalTempFile.exists()) {
                        finalTempFile.delete()
                        Log.d(TAG, "🗑️ 임시 오디오 파일 삭제 (오류 발생)")
                    }
                    onCompletion?.invoke()  // 오류 발생 시에도 콜백 호출
                    false
                }
                
                // 재생 시작
                Log.d(TAG, "▶️ MediaPlayer start() 호출 중...")
                player.start()
                mediaPlayer = player
                Log.i(TAG, "▶️ 로컬 오디오 재생 시작: $fileName")
                Log.d(TAG, "   MediaPlayer 상태: isPlaying=${player.isPlaying}, duration=${player.duration}ms")
                
            } catch (e: java.io.IOException) {
                Log.e(TAG, "❌ MediaPlayer prepare() 실패: ${e.message}")
                e.printStackTrace()
                player.release()
                mediaPlayer = null
                // 임시 파일 삭제
                if (finalTempFile.exists()) {
                    finalTempFile.delete()
                }
                onCompletion?.invoke()
            } catch (e: Exception) {
                Log.e(TAG, "❌ MediaPlayer 설정 실패: ${e.message}")
                e.printStackTrace()
                player.release()
                mediaPlayer = null
                // 임시 파일 삭제
                if (finalTempFile.exists()) {
                    finalTempFile.delete()
                }
                onCompletion?.invoke()
            }
            
        } catch (e: java.io.FileNotFoundException) {
            Log.e(TAG, "❌ assets 파일을 찾을 수 없습니다: $fileName")
            e.printStackTrace()
            onCompletion?.invoke()
        } catch (e: Exception) {
            Log.e(TAG, "❌ 로컬 오디오 재생 실패: ${e.message}")
            e.printStackTrace()
            // 임시 파일 정리
            tempFile?.let {
                if (it.exists()) {
                    it.delete()
                }
            }
            onCompletion?.invoke()  // 오류 발생 시에도 콜백 호출
        }
    }
    
    /**
     * MediaPlayer 리소스 정리
     */
    fun cleanup() {
        stop()
    }
}

