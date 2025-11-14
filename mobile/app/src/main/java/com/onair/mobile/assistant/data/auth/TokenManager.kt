package com.onair.mobile.assistant.data.auth

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * 인증 토큰 관리 유틸리티
 * 
 * Spring 서버 액세스 토큰을 SharedPreferences에 저장하고 불러옵니다.
 * REFRESH_TOKEN을 사용하여 ACCESS_TOKEN을 자동으로 갱신합니다.
 */
class TokenManager(private val context: Context) {
    private val TAG = "TokenManager"
    private val preferences: SharedPreferences = 
        context.getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)
    
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()
    
    companion object {
        private const val PREFERENCES_KEY_ACCESS_TOKEN = "access_token"
        private const val PREFERENCES_KEY_REFRESH_TOKEN = "refresh_token"
        
        // TODO: 테스트 완료 후 제거 - REFRESH_TOKEN 하드코딩 (임시)
        private const val HARDCODED_REFRESH_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI0IiwidHlwZSI6InJlZnJlc2giLCJpYXQiOjE3NjI1MjYzMDAsImV4cCI6MTc2Mjk1ODMwMH0.qUJN4pPNkXj1oU0BAqmjsU6HPdzQCpaQaP_KaJemgFQ"  // 여기에 실제 REFRESH_TOKEN 입력
        private const val SPRING_SERVER_URL = "https://onair.ai.kr/api"  // Spring 서버 URL
    }
    
    /**
     * 액세스 토큰 저장
     * 
     * @param token 액세스 토큰
     */
    fun saveAccessToken(token: String) {
        preferences.edit()
            .putString(PREFERENCES_KEY_ACCESS_TOKEN, token)
            .apply()
        Log.d(TAG, "✅ 액세스 토큰 저장 완료")
    }
    
    /**
     * 액세스 토큰 불러오기
     * 
     * @return 저장된 액세스 토큰, 없으면 null
     */
    fun getAccessToken(): String? {
        return preferences.getString(PREFERENCES_KEY_ACCESS_TOKEN, null)
    }
    
    /**
     * 액세스 토큰 삭제 (로그아웃 시)
     */
    fun clearAccessToken() {
        preferences.edit()
            .remove(PREFERENCES_KEY_ACCESS_TOKEN)
            .apply()
        Log.d(TAG, "🗑️ 액세스 토큰 삭제 완료")
    }
    
    /**
     * 토큰 존재 여부 확인
     */
    fun hasToken(): Boolean {
        return getAccessToken() != null
    }
    
    /**
     * REFRESH_TOKEN 저장 (임시 테스트용)
     * 
     * TODO: 테스트 완료 후 제거 - 실제 로그인 API에서 받아와야 함
     */
    fun saveRefreshToken(token: String) {
        preferences.edit()
            .putString(PREFERENCES_KEY_REFRESH_TOKEN, token)
            .apply()
        Log.d(TAG, "✅ REFRESH_TOKEN 저장 완료")
    }
    
    /**
     * REFRESH_TOKEN 불러오기
     */
    fun getRefreshToken(): String? {
        return preferences.getString(PREFERENCES_KEY_REFRESH_TOKEN, null)
    }
    
    /**
     * REFRESH_TOKEN 삭제
     */
    fun clearRefreshToken() {
        preferences.edit()
            .remove(PREFERENCES_KEY_REFRESH_TOKEN)
            .apply()
        Log.d(TAG, "🗑️ REFRESH_TOKEN 삭제 완료")
    }
    
    /**
     * REFRESH_TOKEN으로 ACCESS_TOKEN 갱신
     * 
     * @param refreshToken REFRESH_TOKEN (null이면 저장된 토큰 사용)
     * @return 갱신 성공 여부
     */
    suspend fun refreshAccessToken(refreshToken: String? = null): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val token = refreshToken ?: getRefreshToken() ?: run {
                    Log.e(TAG, "❌ REFRESH_TOKEN이 없습니다.")
                    return@withContext false
                }
                
                // Spring 서버 토큰 갱신 API 호출
                val url = if (SPRING_SERVER_URL.endsWith("/")) {
                    "${SPRING_SERVER_URL}auth/refresh"
                } else {
                    "$SPRING_SERVER_URL/auth/refresh"
                }
                
                val requestBody = JSONObject().apply {
                    put("refreshToken", token)
                }.toString()
                
                val request = Request.Builder()
                    .url(url)
                    .post(requestBody.toRequestBody("application/json".toMediaType()))
                    .addHeader("Content-Type", "application/json")
                    .build()
                
                val response = httpClient.newCall(request).execute()
                
                if (!response.isSuccessful) {
                    Log.e(TAG, "❌ 토큰 갱신 실패: HTTP ${response.code}")
                    response.body?.let { body ->
                        Log.e(TAG, "응답: ${body.string()}")
                    }
                    return@withContext false
                }
                
                val responseBody = response.body?.string() ?: run {
                    Log.e(TAG, "❌ 응답 본문이 비어있습니다.")
                    return@withContext false
                }
                
                val json = JSONObject(responseBody)
                val newAccessToken = json.optString("accessToken", "")
                
                if (newAccessToken.isEmpty()) {
                    Log.e(TAG, "❌ 새로운 ACCESS_TOKEN이 응답에 없습니다.")
                    return@withContext false
                }
                
                // 새로운 ACCESS_TOKEN 저장
                saveAccessToken(newAccessToken)
                Log.i(TAG, "✅ ACCESS_TOKEN 갱신 완료")
                
                // REFRESH_TOKEN도 갱신되었을 수 있음
                val newRefreshToken = json.optString("refreshToken", "")
                if (newRefreshToken.isNotEmpty()) {
                    saveRefreshToken(newRefreshToken)
                    Log.i(TAG, "✅ REFRESH_TOKEN 갱신 완료")
                }
                
                true
            } catch (e: Exception) {
                Log.e(TAG, "❌ 토큰 갱신 오류: ${e.message}")
                e.printStackTrace()
                false
            }
        }
    }
    
    /**
     * 하드코딩된 REFRESH_TOKEN 설정 (임시 테스트용)
     * 
     * TODO: 테스트 완료 후 이 메서드 호출 부분 제거
     */
    fun setupHardcodedRefreshToken() {
        if (HARDCODED_REFRESH_TOKEN.isNotEmpty() && HARDCODED_REFRESH_TOKEN != "YOUR_REFRESH_TOKEN_HERE") {
            saveRefreshToken(HARDCODED_REFRESH_TOKEN)
            Log.i(TAG, "✅ 하드코딩된 REFRESH_TOKEN 설정 완료")
        } else {
            Log.w(TAG, "⚠️ 하드코딩된 REFRESH_TOKEN이 설정되지 않았습니다.")
            Log.w(TAG, "   TokenManager.kt의 HARDCODED_REFRESH_TOKEN 상수를 수정하세요.")
        }
    }
    
    /**
     * ACCESS_TOKEN이 만료되었는지 확인하고 필요시 갱신
     * 
     * @return 유효한 ACCESS_TOKEN (갱신 후 또는 기존)
     */
    suspend fun ensureValidAccessToken(): String? {
        val currentToken = getAccessToken()
        
        // TODO: 실제로는 ACCESS_TOKEN의 만료 시간을 확인해야 함
        // 현재는 토큰이 없으면 갱신 시도
        if (currentToken == null) {
            Log.i(TAG, "🔄 ACCESS_TOKEN이 없어 REFRESH_TOKEN으로 갱신 시도")
            val refreshed = refreshAccessToken()
            if (refreshed) {
                return getAccessToken()
            }
        }
        
        return currentToken
    }
}

