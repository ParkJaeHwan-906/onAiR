package com.onair.mobile.assistant.data.auth

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import com.onair.mobile.communicate.PreferenceUtil
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
 * 실제 로그인 플로우에서 받은 RefreshToken을 사용합니다.
 */
class TokenManager(private val context: Context) {
    private val TAG = "TokenManager"
    private val preferences: SharedPreferences = 
        context.getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)
    
    // 실제 로그인 플로우에서 사용하는 PreferenceUtil 사용
    private val preferenceUtil = PreferenceUtil(context)
    
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()
    
    companion object {
        private const val PREFERENCES_KEY_ACCESS_TOKEN = "access_token"
        private const val PREFERENCES_KEY_REFRESH_TOKEN = "refresh_token"
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
     * REFRESH_TOKEN 저장
     * 실제 로그인 플로우의 PreferenceUtil에 저장합니다.
     */
    fun saveRefreshToken(token: String) {
        // 실제 로그인 플로우에서 사용하는 PreferenceUtil에 저장
        preferenceUtil.setRefreshToken(token)
        // 레거시 호환성을 위해 기존 SharedPreferences에도 저장
        preferences.edit()
            .putString(PREFERENCES_KEY_REFRESH_TOKEN, token)
            .apply()
        Log.d(TAG, "✅ REFRESH_TOKEN 저장 완료")
    }
    
    /**
     * REFRESH_TOKEN 불러오기
     * 실제 로그인 플로우에서 저장된 RefreshToken을 사용합니다.
     */
    fun getRefreshToken(): String? {
        // 먼저 실제 로그인 플로우에서 저장된 RefreshToken 확인
        val refreshTokenFromLogin = preferenceUtil.getRefreshToken()
        if (refreshTokenFromLogin.isNotEmpty()) {
            return refreshTokenFromLogin
        }
        // 레거시 SharedPreferences에서 확인 (하위 호환성)
        return preferences.getString(PREFERENCES_KEY_REFRESH_TOKEN, null)
    }
    
    /**
     * REFRESH_TOKEN 삭제
     */
    fun clearRefreshToken() {
        // 실제 로그인 플로우의 PreferenceUtil에서 RefreshToken만 삭제 (빈 문자열로 설정)
        preferenceUtil.setRefreshToken("")
        // 레거시 호환성을 위해 기존 SharedPreferences에서도 삭제
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
                    // 실제 로그인 플로우의 PreferenceUtil에 저장
                    preferenceUtil.setRefreshToken(newRefreshToken)
                    // 레거시 호환성을 위해 기존 SharedPreferences에도 저장
                    preferences.edit()
                        .putString(PREFERENCES_KEY_REFRESH_TOKEN, newRefreshToken)
                        .apply()
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

