package com.onair.mobile.communicate.data

import android.util.Log
import com.onair.mobile.communicate.data.api.ApiService
import com.onair.mobile.communicate.data.api.dto.TaskResponse
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class TaskRepository(
    private val apiService: ApiService
) {
    fun getCompletedTaskList(action: Int, onResult: (Result<List<TaskResponse>>) -> Unit) {
        apiService.getTaskList(action).enqueue(object : Callback<List<TaskResponse>>{
            override fun onResponse(
                call: Call<List<TaskResponse>?>,
                response: Response<List<TaskResponse>?>
            ) {
                if (response.isSuccessful) {
                    val taskList = response.body()
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
                call: Call<List<TaskResponse>?>,
                t: Throwable
            ) {
                Log.e("task list", t.message.toString())
                onResult(Result.failure(t))
            }
        })
    }
}