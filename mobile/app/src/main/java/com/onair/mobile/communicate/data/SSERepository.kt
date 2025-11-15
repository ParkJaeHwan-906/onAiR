package com.onair.mobile.communicate.data

import android.util.Log
import com.launchdarkly.eventsource.MessageEvent
import com.launchdarkly.eventsource.background.BackgroundEventHandler
import com.onair.mobile.communicate.data.sse.SseClient
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import org.json.JSONObject

class SSERepository(
    private val sseClient: SseClient
) : BackgroundEventHandler {

    private val _eventFlow = MutableSharedFlow<SseEvent>(
        replay = 1,
        extraBufferCapacity = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    val eventFlow = _eventFlow.asSharedFlow()

    fun startSSE() {
        sseClient.initSSE(this)
    }
    fun stopSSE() {
        sseClient.disconnect()
    }
    override fun onOpen() {
        Log.d("SSE", "연결")
    }

    override fun onClosed() {
        Log.d("SSE", "연결 종료")
    }

    override fun onMessage(
        event: String?,
        messageEvent: MessageEvent?
    ) {
        val data = messageEvent?.data ?: return
        Log.d("SSE", data)
        
        // timestamp, connected 같은 문자열은 JSON이 아니므로 스킵
        if (data.trim().startsWith("{") && data.trim().endsWith("}")) {
            val json = try {
                JSONObject(data)
            } catch (e: Exception) {
                Log.e("SSE", "JSON 파싱 실패: ${e.message}")
                return
            }
            when (event) {
                "callRequest" -> _eventFlow.tryEmit(SseEvent.CallRequest(json))
                "taskAssign" -> _eventFlow.tryEmit(SseEvent.TaskAssign(json))
                "taskCancel" -> _eventFlow.tryEmit(SseEvent.TaskCancel(json))
                "rtcCanceled" -> {
                    // rtcCanceled 이벤트는 처리하되 로그만 남김
                    Log.d("SSE", "이벤트 rtcCanceled 수신 $data")
                }
                else -> {
                    Log.w("SSE", "알 수 없는 이벤트 수신: $event")
                }
            }
            Log.d("SSE", "이벤트 $event 수신 ${messageEvent?.data}")
        } else {
            // JSON이 아닌 문자열 데이터 (timestamp, connected 등)는 무시
            Log.d("SSE", "문자열 데이터 수신 (JSON 아님): $data")
        }
    }

    override fun onComment(comment: String?) {
//                TODO("Not yet implemented")
    }

    override fun onError(t: Throwable?) {
        Log.e("SSE", "오류: ${t?.message}")
    }
}
sealed class SseEvent {
    data class CallRequest(val data: JSONObject) : SseEvent()
    data class CallResponse(val data: JSONObject) : SseEvent()
    data class TaskAssign(val data: JSONObject) : SseEvent()
    data class TaskCancel(val data: JSONObject) : SseEvent()
}