package com.onair.mobile.assistant.data.task

import android.util.Log
import com.google.gson.Gson
import kotlinx.coroutines.*
import okhttp3.*
import okio.BufferedSource
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * SSE (Server-Sent Events) 클라이언트
 * 
 * 작업 실시간 현황 조회를 위한 SSE 연결
 * 엔드포인트: /task/stream
 */
class SseTaskClient(
    private val baseUrl: String,
    private val accessToken: String,
    private val onConnect: () -> Unit,
    private val onTaskAssign: (TaskAssignEvent) -> Unit,
    private val onTaskCancel: (TaskCancelEvent) -> Unit,
    private val onTaskEnd: (TaskEndEvent) -> Unit,
    private val onError: (Throwable) -> Unit
) {
    private val TAG = "SseTaskClient"
    private val gson = Gson()
    private var client: OkHttpClient? = null
    private var request: Request? = null
    private var call: Call? = null
    private var isConnected = false
    private var job: Job? = null
    
    /**
     * SSE 연결 시작
     */
    fun connect() {
        if (isConnected) {
            Log.w(TAG, "⚠️ 이미 연결되어 있습니다.")
            return
        }
        
        job = CoroutineScope(Dispatchers.IO).launch {
            try {
                val url = if (baseUrl.endsWith("/")) {
                    "${baseUrl}task/stream"
                } else {
                    "$baseUrl/task/stream"
                }
                
                Log.i(TAG, "🔌 SSE 연결 시작: $url")
                
                client = OkHttpClient.Builder()
                    .connectTimeout(30, TimeUnit.SECONDS)
                    .readTimeout(0, TimeUnit.SECONDS)  // SSE는 무한 대기
                    .writeTimeout(30, TimeUnit.SECONDS)
                    .build()
                
                request = Request.Builder()
                    .url(url)
                    .addHeader("Authorization", "Bearer $accessToken")
                    .addHeader("Accept", "text/event-stream")
                    .addHeader("Cache-Control", "no-cache")
                    .build()
                
                call = client!!.newCall(request!!)
                val response = call!!.execute()
                
                if (!response.isSuccessful) {
                    throw IOException("SSE 연결 실패: HTTP ${response.code}")
                }
                
                val responseBody = response.body ?: throw IOException("Response body가 null입니다.")
                val source = responseBody.source()
                
                isConnected = true
                Log.i(TAG, "✅ SSE 연결 성공")
                onConnect()
                
                // SSE 이벤트 스트림 읽기
                readEventStream(source)
                
            } catch (e: Exception) {
                Log.e(TAG, "❌ SSE 연결 실패: ${e.message}")
                isConnected = false
                onError(e)
            }
        }
    }
    
    /**
     * SSE 이벤트 스트림 읽기
     */
    private suspend fun readEventStream(source: BufferedSource) {
        var eventType: String? = null
        var data: StringBuilder? = null
        
        try {
            while (isConnected && !source.exhausted()) {
                val line = source.readUtf8Line() ?: break
                
                when {
                    line.isEmpty() -> {
                        // 빈 줄 = 이벤트 완료
                        if (eventType != null && data != null) {
                            handleEvent(eventType, data.toString())
                        }
                        eventType = null
                        data = null
                    }
                    line.startsWith("event:") -> {
                        eventType = line.substring(6).trim()
                    }
                    line.startsWith("data:") -> {
                        if (data == null) {
                            data = StringBuilder()
                        }
                        data.append(line.substring(5).trim())
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ SSE 스트림 읽기 오류: ${e.message}")
            isConnected = false
            onError(e)
        }
    }
    
    /**
     * SSE 이벤트 처리
     */
    private fun handleEvent(eventType: String, data: String) {
        try {
            Log.d(TAG, "📩 SSE 이벤트 수신: event=$eventType, data=$data")
            
            when (eventType) {
                "connect" -> {
                    Log.i(TAG, "✅ SSE 연결 확인: $data")
                }
                "taskAssign" -> {
                    val event = gson.fromJson(data, TaskAssignEvent::class.java)
                    Log.i(TAG, "📋 작업 할당: taskId=${event.assignedTaskId}, userId=${event.assignedUserAccountId}, userName=${event.assignedUserName}")
                    onTaskAssign(event)
                }
                "taskCancel" -> {
                    val event = gson.fromJson(data, TaskCancelEvent::class.java)
                    Log.i(TAG, "❌ 작업 취소: taskId=${event.TaskId}")
                    onTaskCancel(event)
                }
                "taskEnd" -> {
                    val event = gson.fromJson(data, TaskEndEvent::class.java)
                    Log.i(TAG, "✅ 작업 완료: taskId=${event.TaskId}")
                    onTaskEnd(event)
                }
                else -> {
                    Log.w(TAG, "⚠️ 알 수 없는 이벤트 타입: $eventType")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ 이벤트 처리 오류: ${e.message}")
            e.printStackTrace()
        }
    }
    
    /**
     * SSE 연결 종료
     */
    fun disconnect() {
        Log.i(TAG, "🛑 SSE 연결 종료")
        isConnected = false
        call?.cancel()
        job?.cancel()
        client = null
        request = null
        call = null
    }
    
    /**
     * 연결 상태 확인
     */
    fun isConnected(): Boolean = isConnected
}

/**
 * SSE 이벤트 데이터 클래스
 */
data class TaskAssignEvent(
    val assignedTaskId: String,
    val assignedUserAccountId: String,
    val assignedUserName: String
)

data class TaskCancelEvent(
    val TaskId: String
)

data class TaskEndEvent(
    val TaskId: String
)

