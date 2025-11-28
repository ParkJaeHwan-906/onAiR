package com.onair.mobile.communicate.data.source.remote.api

import com.onair.mobile.communicate.data.model.dto.LoginRequest
import com.onair.mobile.communicate.data.model.dto.ApiResponse
import com.onair.mobile.communicate.data.model.dto.CallRequestRequest
import com.onair.mobile.communicate.data.model.dto.CallResponseRequestDto
import com.onair.mobile.communicate.data.model.dto.RefreshRequest
import com.onair.mobile.communicate.data.model.dto.EndTaskRequest
import com.onair.mobile.communicate.data.model.dto.RtcResponse
import com.onair.mobile.communicate.data.model.dto.TaskResponse
import com.onair.mobile.communicate.data.model.dto.TokenData
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

    @POST("webrtc/request")
    fun requestCall(
        @Body body: CallRequestRequest
    ): Call<ApiResponse<RtcResponse>>
}