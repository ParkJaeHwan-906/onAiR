package com.onair.mobile.communicate.data

import android.util.Log
import com.onair.mobile.communicate.PreferenceUtil
import com.onair.mobile.communicate.data.api.ApiService
import com.onair.mobile.communicate.data.api.dto.ApiResponse
import com.onair.mobile.communicate.data.api.dto.LoginRequest
import com.onair.mobile.communicate.data.api.dto.RefreshRequest
import com.onair.mobile.communicate.data.api.dto.TokenData
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import java.lang.Exception

class AuthRepository(
    private val apiService: ApiService,
    private val dataStore: PreferenceUtil
) {
//    suspend fun login(email: String, password: String): ApiResponse<Unit> {
//        return try {
//            val response = apiService.login(LoginRequest(email, password))
//            if (response.isSuccessful) {
//                val token = response.body()?.accessToken ?: return ApiResponse.Error("토큰없음")
//                dataStore.setToken(token, "")  //saveAccessToken 변경 고려
//                ApiResponse.Success(Unit)
//            }
//            else {
//                ApiResponse.Error("로그인 실패", response.code())
//
//            }
//        } catch (e: Exception) {
//            ApiResponse.Error(e.message)
//        }
//    }
    fun login(email: String, password : String, onResult: (Result<Unit>) -> Unit) {
        apiService.login(LoginRequest(email, password)).enqueue(object : Callback<ApiResponse<TokenData>> {
            override fun onResponse(
                call: Call<ApiResponse<TokenData>?>,
                response: Response<ApiResponse<TokenData>?>
            ) {
                if (response.isSuccessful && response.body()?.success == true) {
                    val data = response.body()?.data
                    if (data != null) {
                        val accessToken = data.accessToken
                        val refreshToken = data.refreshToken
                        dataStore.setAccessToken(accessToken.toString())
                        dataStore.setRefreshToken(refreshToken.toString())
                        onResult(Result.success(Unit))
                    }
                    else {
                        onResult(Result.failure(kotlin.Exception("토큰이 비어 있음")))
                    }
                } else {
                    onResult(Result.failure(Exception("로그인 실패 : ${response.message()}")))
                }
            }

            override fun onFailure(
                call: Call<ApiResponse<TokenData>?>,
                t: Throwable
            ) {
                Log.e("ticket", t.message.toString())
                onResult(Result.failure(t))
            }

        })
    }
    fun getRefreshToken(): String {
        return dataStore.getRefreshToken()
    }
    fun getAccessToken(): String {
        return dataStore.getAccessToken()
    }
    fun refreshAccessToken(refreshToken : String, onResult: (Result<Unit>) -> Unit) {
        apiService.refresh(RefreshRequest(refreshToken)).enqueue(object : Callback<ApiResponse<TokenData>>{
            override fun onResponse(
                call: Call<ApiResponse<TokenData>?>,
                response: Response<ApiResponse<TokenData>?>
            ) {
                if (response.isSuccessful && response.body()?.success == true) {
                    val data = response.body()?.data
                    if (data != null) {
                        val accessToken = data.accessToken
                        val refreshToken = data.refreshToken
                        dataStore.setAccessToken(accessToken.toString())
                        dataStore.setRefreshToken(refreshToken.toString())
                        onResult(Result.success(Unit))
                    }
                    else {
                        onResult(Result.failure(kotlin.Exception("토큰이 비어 있음")))
                    }
                } else {
                    onResult(Result.failure(Exception("로그인 실패 : ${response.message()}")))
                }
            }

            override fun onFailure(
                call: Call<ApiResponse<TokenData>?>,
                t: Throwable
            ) {
                Log.e("ticket", t.message.toString())
                onResult(Result.failure(t))
            }

        })
    }
}