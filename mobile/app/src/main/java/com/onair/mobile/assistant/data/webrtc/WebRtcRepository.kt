package com.onair.mobile.assistant.data.webrtc

import android.util.Log
import com.onair.mobile.assistant.core.model.dto.WebRtcRequestDto
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.create

/**
 * WebRTC API Repository 구현체
 */
class WebRtcRepository(
    private val baseUrl: String  // 예: "https://onair.ai.kr/api"
) {
    private val TAG = "WebRtcRepository"
    
    private val api: WebRtcApi by lazy {
        // Retrofit의 baseUrl은 반드시 끝에 슬래시(/)가 있어야 함
        val normalizedBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        
        Retrofit.Builder()
            .baseUrl(normalizedBaseUrl)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(WebRtcApi::class.java)
    }
    
    /**
     * WebRTC 연결 요청
     * 
     * @param accessToken 액세스 토큰
     * @param receiverAccountId 수신자 계정 ID
     */
    suspend fun requestConnection(accessToken: String, receiverAccountId: Long): Boolean {
        return try {
            Log.d(TAG, "📡 WebRTC 연결 요청: receiverAccountId=$receiverAccountId")
            
            val request = WebRtcRequestDto(receiverAccountId = receiverAccountId)
            val authorization = "Bearer $accessToken"
            val response = api.requestConnection(authorization, request)
            
            if (response.isSuccessful) {
                Log.i(TAG, "✅ WebRTC 연결 요청 성공: receiverAccountId=$receiverAccountId")
                true
            } else {
                Log.e(TAG, "❌ WebRTC 연결 요청 실패: ${response.code()} ${response.message()}")
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ WebRTC 연결 요청 오류: ${e.message}")
            e.printStackTrace()
            false
        }
    }
}

