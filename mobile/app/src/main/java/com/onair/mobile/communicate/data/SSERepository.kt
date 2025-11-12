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
        val json = try {
            JSONObject(data)
        } catch (e: Exception) {
            Log.e("SSE", "JSON 파싱 실패: ${e.message}")
            return
            TODO("Json 말고 Data class로 변환 고려")
        }
        when (event) {
            "callRequest" -> _eventFlow.tryEmit(SseEvent.CallRequest(json))
            "taskAssign" -> _eventFlow.tryEmit(SseEvent.TaskAssign(json))
            "taskCancel" -> _eventFlow.tryEmit(SseEvent.TaskCancel(json))
            else -> {
                Log.w("SSE", "알 수 없는 이벤트 수신: $event")
            }
        }
        Log.d("SSE", "이벤트 $event 수신 ${messageEvent?.data}")
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
    data class TaskAssign(val data: JSONObject) : SseEvent()
    data class TaskCancel(val data: JSONObject) : SseEvent()
}