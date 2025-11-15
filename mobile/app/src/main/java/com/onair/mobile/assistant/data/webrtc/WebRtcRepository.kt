package com.onair.mobile.assistant.data.webrtc

import android.util.Log
import com.onair.mobile.assistant.core.model.dto.WebRtcRequestDto
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.create
import java.util.concurrent.TimeUnit

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
        
        // HTTP 로깅 인터셉터 추가 (실제 HTTP 요청/응답 확인용)
        val loggingInterceptor = HttpLoggingInterceptor { message ->
            Log.d(TAG, "🌐 HTTP: $message")
        }.apply {
            level = HttpLoggingInterceptor.Level.BODY
        }
        
        val okHttpClient = OkHttpClient.Builder()
            .addInterceptor(loggingInterceptor)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
        
        Log.i(TAG, "🔧 Retrofit 초기화: baseUrl=$normalizedBaseUrl")
        
        Retrofit.Builder()
            .baseUrl(normalizedBaseUrl)
            .client(okHttpClient)
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
            Log.i(TAG, "📡 WebRTC 연결 요청 시작")
            Log.d(TAG, "   - receiverAccountId: $receiverAccountId")
            Log.d(TAG, "   - accessToken 길이: ${accessToken.length}")
            Log.d(TAG, "   - accessToken 앞 20자: ${accessToken.take(20)}...")
            
            val request = WebRtcRequestDto(receiverAccountId = receiverAccountId)
            val authorization = "Bearer $accessToken"
            
            // 실제 요청 URL 확인
            val normalizedBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
            val fullUrl = "${normalizedBaseUrl}webrtc/request"
            
            Log.i(TAG, "📤 POST 요청 전송")
            Log.i(TAG, "   - Full URL: $fullUrl")
            Log.d(TAG, "   - Authorization: Bearer ${accessToken.take(20)}...")
            Log.d(TAG, "   - Request Body: {receiverAccountId: $receiverAccountId}")
            
            val response = api.requestConnection(authorization, request)
            
            Log.d(TAG, "📥 서버 응답 수신")
            Log.d(TAG, "   - Status Code: ${response.code()}")
            Log.d(TAG, "   - Status Message: ${response.message()}")
            Log.d(TAG, "   - isSuccessful: ${response.isSuccessful}")
            
            if (response.isSuccessful) {
                Log.i(TAG, "✅ WebRTC 연결 요청 성공: receiverAccountId=$receiverAccountId, statusCode=${response.code()}")
                true
            } else {
                val errorBody = response.errorBody()?.string()
                Log.e(TAG, "❌ WebRTC 연결 요청 실패")
                Log.e(TAG, "   - Status Code: ${response.code()}")
                Log.e(TAG, "   - Status Message: ${response.message()}")
                Log.e(TAG, "   - Error Body: $errorBody")
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ WebRTC 연결 요청 오류 발생")
            Log.e(TAG, "   - Exception Type: ${e.javaClass.simpleName}")
            Log.e(TAG, "   - Exception Message: ${e.message}")
            e.printStackTrace()
            false
        }
    }
}

