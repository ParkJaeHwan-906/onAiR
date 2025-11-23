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
import java.net.Socket

class WorkingViewModel(
    private val taskRepository: TaskRepository,
    private val workingRepository: WorkingRepository
): ViewModel() {
//    enum class OnAirState {
//        WAITING_WAKEWORD,
//        WAKEWORD_DETECTED,
//        PROCESSING_AI,
//        PROCESSING_OPERATOR
//    }
    private val _endStatus = MutableStateFlow(false)
    val endStatus = _endStatus.asStateFlow()
    private val _liveKitToken = MutableStateFlow("")
    val liveKitToken = _liveKitToken.asStateFlow()
    private val _onAirState = MutableStateFlow<OnAirState>(OnAirState.Waiting)
    val onAirState = _onAirState.asStateFlow()
    val finalAnswer = SocketHolder.socketClient.finalAnswer
    val cvAnswer = SocketHolder.socketClient.cvAnswer
    val endService = SocketHolder.socketClient.endService

    init {
        viewModelScope.launch {
            SocketHolder.socketClient.wakewordFlow.collect {
                if (_onAirState.value == OnAirState.Waiting) {
                    _onAirState.value = OnAirState.Started
                }
            }
        }
    }


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
    fun requestCall() {
        viewModelScope.launch {
            workingRepository.requestCall { result ->
                result.onSuccess {
                    Log.i("request call", "통신 연결 요청 성공")
                }.onFailure { exception ->
                    Log.e("request call", exception.message.toString())
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

    fun onWakewordDetected() {
        if (_onAirState.value == OnAirState.Waiting) {
            _onAirState.value = OnAirState.Started
        }
    }
    fun onServiceStarted() {
        _onAirState.value = OnAirState.Processing
    }
    fun onFlowCompleted() {
        _onAirState.value = OnAirState.Waiting
    }
}
sealed class OnAirState {
    object Waiting : OnAirState()
    object Started : OnAirState()
    object Processing : OnAirState()
}
