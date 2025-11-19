package com.onair.mobile.communicate.presentation.ui

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onair.mobile.communicate.data.SseEvent
import com.onair.mobile.communicate.data.TaskRepository
import com.onair.mobile.communicate.data.WorkingRepository
import com.onair.mobile.communicate.data.source.remote.SocketHolder
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import org.json.JSONObject

class WorkingViewModel(
    private val taskRepository: TaskRepository,
    private val workingRepository: WorkingRepository
): ViewModel() {
    private val _endStatus = MutableStateFlow(false)
    val endStatus = _endStatus.asStateFlow()
    private val _liveKitToken = MutableStateFlow("")
    val liveKitToken = _liveKitToken.asStateFlow()
    val finalAnswer = SocketHolder.socketClient.finalAnswer
    val cvAnswer = SocketHolder.socketClient.cvAnswer

    fun endTask(taskId: Long, solution: String) {
        viewModelScope.launch {
            taskRepository.endTask(taskId, solution) { result ->
                result.onSuccess {
                    _endStatus.value = true
                }.onFailure {

                }
            }
        }
    }

    fun responseCall(senderId: Long, senderName: String, accept: Boolean) {
        viewModelScope.launch {
            workingRepository.responseCall(senderId, senderName, accept) {result ->
                result.onSuccess { accessToken ->
                    _liveKitToken.value = accessToken.toString()
                }.onFailure { e ->
                    Log.e("response call", e.message.toString())
                }
            }
        }
    }
    fun getLiveKitToken(data: JSONObject) {
        val acceptConnect = data.getBoolean("acceptConnection")
        if (acceptConnect) {
            _liveKitToken.value = data.getString("accessToken")
        } else {
            Log.e("Live kit", "요청이 거절됨")
        }
    }
}