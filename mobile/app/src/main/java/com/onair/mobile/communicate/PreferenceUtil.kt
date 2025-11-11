package com.onair.mobile.communicate

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit

class PreferenceUtil(context: Context) {
    private val preferences: SharedPreferences = context.getSharedPreferences("livekit", Context.MODE_PRIVATE)
    fun getAccessToken() : String {
        return preferences.getString("ACCESS_TOKEN", "").toString()
    }
    fun setAccessToken(value: String) {
        preferences.edit { putString("ACCESS_TOKEN", value).apply() }
    }
    fun getRefreshToken() : String {
        return preferences.getString("REFRESH_TOKEN", "").toString()
    }
    fun setRefreshToken(value: String) {
        preferences.edit { putString("REFRESH_TOKEN", value).apply() }
    }
    fun reset() {
        preferences.edit { clear() }
    }

    companion object {

    }
}