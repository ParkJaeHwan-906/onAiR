package com.onair.mobile.communicate.data.api

import com.onair.mobile.communicate.data.api.dto.LoginRequest
import com.onair.mobile.communicate.data.api.dto.LoginResponse
import com.onair.mobile.communicate.data.api.dto.RefreshRequest
import com.onair.mobile.communicate.data.api.dto.TaskResponse
import retrofit2.Call
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface ApiService {
    @POST("login")
    fun login(
        @Body body: LoginRequest
//    ): Response<LoginResponse>
    ): Call<LoginResponse>

    @POST("refresh")
    fun refresh(
        @Body body: RefreshRequest
    ): Call<LoginResponse>

    @GET("task")
    fun getTaskList(
        @Query("action") action: Int
    ): Call<List<TaskResponse>>
}