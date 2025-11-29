package com.onair.mobile.communicate.data

import android.util.Log
import com.onair.mobile.communicate.data.source.remote.api.ApiService
import com.onair.mobile.communicate.data.model.dto.ApiResponse
import com.onair.mobile.communicate.data.model.dto.CallRequestRequest
import com.onair.mobile.communicate.data.model.dto.CallResponseRequestDto
import com.onair.mobile.communicate.data.model.dto.RtcResponse
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class WorkingRepository(
    private val apiService: ApiService
) {
    fun responseCall(senderId: Long, senderName: String, accept: Boolean, onResult: (Result<String?>) -> Unit) {
        val dto = CallResponseRequestDto(accept, senderId, senderName)
        apiService.responseCall(dto).enqueue( object : Callback<ApiResponse<RtcResponse>> {
            override fun onResponse(
                call: Call<ApiResponse<RtcResponse>?>,
                response: Response<ApiResponse<RtcResponse>?>
            ) {
                if (response.isSuccessful && response.body()?.success == true) {
                    if (!response.body()?.data?.accessToken.isNullOrBlank()) {
                        Log.d("RTC repo", "토큰 ${response.body()?.data?.accessToken}")
                        onResult(Result.success(response.body()?.data?.accessToken.toString()))
                    } else {
                        onResult(Result.failure(Exception("토큰이 없습니다.")))
                    }
                } else {
                    onResult(Result.failure(Exception(response.message())))
                }
            }

            override fun onFailure(
                call: Call<ApiResponse<RtcResponse>?>,
                t: Throwable
            ) {
                onResult(Result.failure(Exception(t.message)))
            }

        })
    }
    fun requestCall(onResult: (Result<String?>) -> Unit) {
        apiService.requestCall(CallRequestRequest(-1)).enqueue(object : Callback<ApiResponse<RtcResponse>> {
            override fun onResponse(
                call: Call<ApiResponse<RtcResponse>?>,
                response: Response<ApiResponse<RtcResponse>?>
            ) {
                if (response.isSuccessful && response.body()?.success == true) {
                    onResult(Result.success(null))
                } else {
                    onResult(Result.failure(Exception("통신 요청에 실패하였습니다.")))
                }
            }

            override fun onFailure(
                call: Call<ApiResponse<RtcResponse>?>,
                t: Throwable
            ) {
                onResult(Result.failure(Exception("통신 요청에 실패하였습니다: ${t.message}")))
            }

        })
    }
}