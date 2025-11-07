package com.onair.mobile.assistant.data.auth

import android.content.Context
import android.content.SharedPreferences
import android.util.Log

/**
 * 인증 토큰 관리 유틸리티
 * 
 * Spring 서버 액세스 토큰을 SharedPreferences에 저장하고 불러옵니다.
 */
class TokenManager(private val context: Context) {
    private val TAG = "TokenManager"
    private val preferences: SharedPreferences = 
        context.getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)
    
    companion object {
        private const val PREFERENCES_KEY_ACCESS_TOKEN = "access_token"
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
}

