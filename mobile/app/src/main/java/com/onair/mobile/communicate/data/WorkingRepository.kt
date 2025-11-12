package com.onair.mobile.communicate.data

import android.util.Log
import com.onair.mobile.communicate.data.api.ApiService
import com.onair.mobile.communicate.data.api.dto.ApiResponse
import com.onair.mobile.communicate.data.api.dto.CallResponseRequestDto
import com.onair.mobile.communicate.data.api.dto.RtcResponse
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
}