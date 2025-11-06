package com.onair.mobile.assistant.data.raspberry

import android.util.Log
import com.onair.mobile.assistant.core.model.dto.IntentDoneRequest
import com.onair.mobile.assistant.core.model.dto.SttModeRequest
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.create

/**
 * 라즈베리파이 제어 API Repository 구현체
 * 
 * Intent 분류 후 라즈베리파이에 제어 시그널을 전송합니다.
 */
class RaspberryPiControlRepository(
    private val baseUrl: String  // 예: "http://192.168.0.100:5000"
) {
    private val TAG = "RaspberryPiControl"
    
    private val api: RaspberryPiControlApi by lazy {
        // Retrofit의 baseUrl은 반드시 끝에 슬래시(/)가 있어야 함
        val normalizedBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        
        Retrofit.Builder()
            .baseUrl(normalizedBaseUrl)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(RaspberryPiControlApi::class.java)
    }
    
    /**
     * STT 모드 설정
     * 
     * @param mode "buffered" 또는 "streaming"
     */
    suspend fun setSttMode(mode: String): Boolean {
        return try {
            Log.d(TAG, "📡 STT 모드 설정 요청: mode=$mode")
            
            val request = SttModeRequest(mode = mode)
            val response = api.setSttMode(request)
            
            if (response.isSuccessful) {
                Log.i(TAG, "✅ STT 모드 설정 성공: $mode")
                true
            } else {
                Log.e(TAG, "❌ STT 모드 설정 실패: ${response.code()} ${response.message()}")
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ STT 모드 설정 오류: ${e.message}")
            e.printStackTrace()
            false
        }
    }
    
    /**
     * Intent 분기 완료 알림
     * 
     * @param branch "AI_SUPPORTER" 또는 "OPERATOR"
     */
    suspend fun notifyIntentDone(branch: String): Boolean {
        return try {
            Log.d(TAG, "📡 Intent 분기 완료 알림: branch=$branch")
            
            val request = IntentDoneRequest(branch = branch)
            val response = api.notifyIntentDone(request)
            
            if (response.isSuccessful) {
                Log.i(TAG, "✅ Intent 분기 완료 알림 성공: $branch")
                true
            } else {
                Log.e(TAG, "❌ Intent 분기 완료 알림 실패: ${response.code()} ${response.message()}")
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ Intent 분기 완료 알림 오류: ${e.message}")
            e.printStackTrace()
            false
        }
    }
}

