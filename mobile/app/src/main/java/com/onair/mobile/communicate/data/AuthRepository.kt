package com.onair.mobile.communicate.data

import android.health.connect.datatypes.units.BloodGlucose
import android.util.Log
import com.onair.mobile.communicate.PreferenceUtil
import com.onair.mobile.communicate.data.api.ApiResponse
import com.onair.mobile.communicate.data.api.ApiService
import com.onair.mobile.communicate.data.api.dto.LoginRequest
import com.onair.mobile.communicate.data.api.dto.LoginResponse
import com.onair.mobile.communicate.data.api.dto.RefreshRequest
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import retrofit2.http.Tag
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
        apiService.login(LoginRequest(email, password)).enqueue(object : Callback<LoginResponse> {
            override fun onResponse(
                call: Call<LoginResponse?>,
                response: Response<LoginResponse?>
            ) {
                if (response.isSuccessful) {
                    val accessToken = response.body()?.accessToken
                    val refreshToken = response.body()?.refreshToken
                    if (!accessToken.isNullOrEmpty()) {
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
                call: Call<LoginResponse?>,
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
        return dataStore.getRefreshToken()
    }
    fun refreshAccessToken(refreshToken : String, onResult: (Result<Unit>) -> Unit) {
        apiService.refresh(RefreshRequest(refreshToken)).enqueue(object : Callback<LoginResponse>{
            override fun onResponse(
                call: Call<LoginResponse?>,
                response: Response<LoginResponse?>
            ) {
                if (response.isSuccessful) {
                    val accessToken = response.body()?.accessToken
                    val refreshToken = response.body()?.refreshToken
                    if (!accessToken.isNullOrEmpty()) {
                        dataStore.setAccessToken(accessToken.toString())
                        dataStore.setRefreshToken(refreshToken.toString())
                        onResult(Result.success(Unit))
                    }else {
                        onResult(Result.failure(kotlin.Exception("토큰이 비어 있음")))
                    }
                } else {
                    onResult(Result.failure(Exception("로그인 실패 : ${response.message()}")))
                }
            }

            override fun onFailure(
                call: Call<LoginResponse?>,
                t: Throwable
            ) {
                Log.e("ticket", t.message.toString())
                onResult(Result.failure(t))
            }

        })
    }
}