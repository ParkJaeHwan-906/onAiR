package com.onair.mobile.communicate.data.api

import com.onair.mobile.communicate.data.api.dto.LoginRequest
import com.onair.mobile.communicate.data.api.dto.ApiResponse
import com.onair.mobile.communicate.data.api.dto.CallResponseRequestDto
import com.onair.mobile.communicate.data.api.dto.RefreshRequest
import com.onair.mobile.communicate.data.api.dto.EndTaskRequest
import com.onair.mobile.communicate.data.api.dto.RtcResponse
import com.onair.mobile.communicate.data.api.dto.TaskResponse
import com.onair.mobile.communicate.data.api.dto.TokenData
import retrofit2.Call
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Headers
import retrofit2.http.PATCH
import retrofit2.http.POST

interface ApiService {
    @Headers("NO_AUTH: true")
    @POST("auth/login")
    fun login(
        @Body body: LoginRequest
//    ): Response<LoginResponse>
    ): Call<ApiResponse<TokenData>>

    @Headers("NO_AUTH: true")
    @POST("auth/refresh")
    fun refresh(
        @Body body: RefreshRequest
    ): Call<ApiResponse<TokenData>>

    @GET("task/list")
    fun getTaskList(): Call<ApiResponse<List<TaskResponse>>>

    @PATCH("task/end")
    fun endTask(
        @Body body: EndTaskRequest
    ): Call<ApiResponse<Boolean>>

    @POST("webrtc/response")
    fun responseCall(
        @Body body: CallResponseRequestDto
    ): Call<ApiResponse<RtcResponse>>
}