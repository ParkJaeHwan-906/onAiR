package com.onair.mobile.communicate.data

import android.util.Log
import com.onair.mobile.communicate.data.api.ApiService
import com.onair.mobile.communicate.data.api.dto.ApiResponse
import com.onair.mobile.communicate.data.api.dto.EndTaskRequest
import com.onair.mobile.communicate.data.api.dto.TaskResponse
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class TaskRepository(
    private val apiService: ApiService
) {
    fun getTaskList(onResult: (Result<List<TaskResponse>>) -> Unit) {
        apiService.getTaskList().enqueue(object : Callback<ApiResponse<List<TaskResponse>>>{
            override fun onResponse(
                call: Call<ApiResponse<List<TaskResponse>>?>,
                response: Response<ApiResponse<List<TaskResponse>>?>
            ) {
                if (response.isSuccessful && response.body()?.success == true) {
                    val taskList = response.body()?.data
                    if (!taskList.isNullOrEmpty()) {
                        onResult(Result.success(taskList))
                    } else {
                        Log.e("task list", response.message().toString())
                        onResult(Result.failure(Exception("할당된 작업이 없음")))
                    }
                } else {
                    onResult(Result.failure(Exception(response.message())))
                }
            }

            override fun onFailure(
                call: Call<ApiResponse<List<TaskResponse>>?>,
                t: Throwable
            ) {
                Log.e("task list", t.message.toString())
                onResult(Result.failure(t))
            }
        })
    }
    fun endTask(taskId: Long, solution: String, onResult: (Result<Boolean>) -> Unit) {
        apiService.endTask(EndTaskRequest(solution, taskId)).enqueue(object : Callback<ApiResponse<Boolean>> {
            override fun onResponse(
                call: Call<ApiResponse<Boolean>?>,
                response: Response<ApiResponse<Boolean>?>
            ) {
                if (response.isSuccessful && response.body()?.success == true) {
                    val end = response.body()?.data
                    if (end == true) {
                        onResult(Result.success(true))
                    } else {
                        onResult(Result.failure(Exception("작업 완료 실패")))
                    }
                } else {
                    onResult(Result.failure(Exception(response.message())))
                }
            }

            override fun onFailure(
                call: Call<ApiResponse<Boolean>?>,
                t: Throwable
            ) {
                Log.e("task end", t.message.toString())
                onResult(Result.failure(t))
            }

        })
    }
}