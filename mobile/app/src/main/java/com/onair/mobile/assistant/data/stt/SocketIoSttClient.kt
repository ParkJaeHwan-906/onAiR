package com.onair.mobile.assistant.data.stt

import android.util.Log
import com.onair.mobile.assistant.core.model.dto.CvDetectionFailedDto
import com.onair.mobile.assistant.core.model.dto.ClarifyQaTurnDto
import com.onair.mobile.assistant.core.model.dto.RagResponse
import com.onair.mobile.assistant.core.model.dto.IntentResultDto
import com.onair.mobile.assistant.core.model.dto.ClarifyTurnDto
import com.onair.mobile.assistant.core.model.dto.FinalAnswerDto
import com.google.gson.Gson
import io.socket.client.IO
import io.socket.client.Socket
import org.json.JSONObject
import java.net.URISyntaxException

/**
 * Socket.IO 클라이언트를 사용하여 Socket.IO 서버에 연결하고 STT 결과 및 Clarify 응답을 수신
 * 
 * Socket.IO 서버에서 다음 이벤트를 수신:
 * - "stt_result": 버퍼링 STT 결과 (Intent 분류용)
 * - "intent_result": Intent 분류 결과 (Gemini-Flash)
 * - "start_sse_connection": SSE 연결 시작 요청
 * - "cv_detection_failed": CV 탐지 실패 이벤트
 * - "clarify_qa_turn": Clarify 질문/답변 턴 수신
 * - "final_answer": 최종 답변 수신
 * 
 * 주의:
 * - Clarify 입력은 모바일에서 전송하지 않음
 * - 라즈베리파이 Streaming STT → FastAPI (직접) → FastAPI가 Socket.IO 서버로 clarify_turn/final_answer 전송
 */
class SocketIoSttClient(
    private val serverUrl: String,  // 예: "http://192.168.0.100:5000"
    private val onSttResult: (String, String, String?) -> Unit,  // (text, type, confidence)
    private val onClarifyResponse: ((RagResponse) -> Unit)? = null,  // Clarify 응답 콜백 (레거시)
    private val onIntentResult: ((IntentResultDto) -> Unit)? = null,  // Intent 결과 콜백 (Gemini-Flash 분류 결과)
    private val onClarifyTurn: ((ClarifyTurnDto) -> Unit)? = null,  // Clarify 턴 콜백
    private val onFinalAnswer: ((FinalAnswerDto) -> Unit)? = null,  // 최종 답변 콜백
    private val onStartSseConnection: ((String?) -> Unit)? = null,  // SSE 연결 시작 요청 콜백
    private val onCvDetectionFailed: ((CvDetectionFailedDto) -> Unit)? = null,  // CV 탐지 실패 콜백
    private val onClarifyQaTurn: ((ClarifyQaTurnDto) -> Unit)? = null  // Clarify 질문/답변 턴 콜백
) {
    private val TAG = "SocketIoSttClient"
    private var socket: Socket? = null
    private var isConnected = false
    private val gson = Gson()
    
    /**
     * Socket.IO 서버에 연결
     * FastAPI 서버에 통합된 Socket.IO 서버에 연결 (경로: /ws)
     */
    fun connect() {
        try {
            val options = IO.Options().apply {
                reconnection = true
                reconnectionAttempts = 5
                reconnectionDelay = 1000
                // FastAPI 서버에 통합된 Socket.IO 서버 경로 설정
                path = "/ws"
            }
            
            socket = IO.socket(serverUrl, options)
            
            // 연결 이벤트
            socket?.on(Socket.EVENT_CONNECT) {
                isConnected = true
                Log.i(TAG, "✅ Socket.IO 서버 연결 성공: $serverUrl (경로: /ws)")
                
                // 디바이스 등록
                registerDevice()
            }
            
            socket?.on(Socket.EVENT_DISCONNECT) {
                isConnected = false
                Log.i(TAG, "🔌 Socket.IO 서버 연결 종료")
            }
            
            socket?.on(Socket.EVENT_CONNECT_ERROR) { args ->
                val error = args?.getOrNull(0)
                Log.e(TAG, "❌ Socket.IO 연결 오류: $error")
                isConnected = false
            }
            
            // stt_result 이벤트 수신
            socket?.on("stt_result") { args ->
                try {
                    val data = args[0] as? JSONObject
                    if (data != null) {
                        val text = data.optString("text", "")
                        val type = data.optString("type", "final")  // "final" | "interim" | "error" | "info"
                        val confidence = data.optDouble("confidence", -1.0)
                        
                        if (text.isNotBlank()) {
                            Log.i(TAG, "📩 STT 결과 수신: type=$type, text=$text")
                            val confidenceStr = if (confidence >= 0) confidence.toString() else null
                            onSttResult(text, type, confidenceStr)
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "❌ STT 결과 처리 오류: ${e.message}")
                    e.printStackTrace()
                }
            }
            
            // intent_result 이벤트 수신 (버퍼링 STT 후 Gemini-Flash Intent 분류 결과)
            socket?.on("intent_result") { args ->
                try {
                    val data = args[0] as? JSONObject
                    if (data != null) {
                        val jsonString = data.toString()
                        Log.d(TAG, "📩 Intent 결과 수신: $jsonString")
                        
                        val intentResult = gson.fromJson(jsonString, IntentResultDto::class.java)
                        onIntentResult?.invoke(intentResult)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "❌ Intent 결과 처리 오류: ${e.message}")
                    e.printStackTrace()
                }
            }
            
            // start_sse_connection 이벤트 수신 (버퍼링 STT 수신 시 SSE 연결 시작 요청)
            socket?.on("start_sse_connection") { args ->
                try {
                    val data = args[0] as? JSONObject
                    if (data != null) {
                        val text = data.optString("text", "")
                        Log.i(TAG, "📡 SSE 연결 시작 요청 수신: text=$text")
                        onStartSseConnection?.invoke(text)
                    } else {
                        Log.i(TAG, "📡 SSE 연결 시작 요청 수신 (데이터 없음)")
                        onStartSseConnection?.invoke(null)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "❌ SSE 연결 시작 요청 처리 오류: ${e.message}")
                    e.printStackTrace()
                }
            }
            
            
            // clarify_turn 이벤트 수신 (Clarify 질문/답변 턴)
            socket?.on("clarify_turn") { args ->
                try {
                    val data = args[0] as? JSONObject
                    if (data != null) {
                        val jsonString = data.toString()
                        Log.d(TAG, "📩 Clarify 턴 수신: $jsonString")
                        
                        val clarifyTurn = gson.fromJson(jsonString, ClarifyTurnDto::class.java)
                        onClarifyTurn?.invoke(clarifyTurn)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "❌ Clarify 턴 처리 오류: ${e.message}")
                    e.printStackTrace()
                }
            }
            
            // final_answer 이벤트 수신 (최종 답변)
            socket?.on("final_answer") { args ->
                try {
                    val data = args[0] as? JSONObject
                    if (data != null) {
                        val jsonString = data.toString()
                        Log.d(TAG, "📩 최종 답변 수신: $jsonString")
                        
                        val finalAnswer = gson.fromJson(jsonString, FinalAnswerDto::class.java)
                        onFinalAnswer?.invoke(finalAnswer)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "❌ 최종 답변 처리 오류: ${e.message}")
                    e.printStackTrace()
                }
            }
            
            // cv_detection_failed 이벤트 수신 (CV 모델 오류 탐지 실패)
            socket?.on("cv_detection_failed") { args ->
                try {
                    val data = args[0] as? JSONObject
                    if (data != null) {
                        val jsonString = data.toString()
                        Log.d(TAG, "📩 CV 탐지 실패 수신: $jsonString")
                        
                        val cvFailed = gson.fromJson(jsonString, CvDetectionFailedDto::class.java)
                        onCvDetectionFailed?.invoke(cvFailed)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "❌ CV 탐지 실패 처리 오류: ${e.message}")
                    e.printStackTrace()
                }
            }
            
            // clarify_qa_turn 이벤트 수신 (Clarify 질문/답변 턴 - 작업자 질문 + LLM 답변)
            socket?.on("clarify_qa_turn") { args ->
                try {
                    val data = args[0] as? JSONObject
                    if (data != null) {
                        val jsonString = data.toString()
                        Log.d(TAG, "📩 Clarify 질문/답변 턴 수신: $jsonString")
                        
                        val qaTurn = gson.fromJson(jsonString, ClarifyQaTurnDto::class.java)
                        onClarifyQaTurn?.invoke(qaTurn)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "❌ Clarify 질문/답변 턴 처리 오류: ${e.message}")
                    e.printStackTrace()
                }
            }
            
            // clarify_response 이벤트 수신 (Clarify 응답 - 레거시)
            socket?.on("clarify_response") { args ->
                try {
                    val data = args[0] as? JSONObject
                    if (data != null) {
                        val jsonString = data.toString()
                        Log.d(TAG, "📩 Clarify 응답 수신 (레거시): $jsonString")
                        
                        val ragResponse = gson.fromJson(jsonString, RagResponse::class.java)
                        onClarifyResponse?.invoke(ragResponse)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "❌ Clarify 응답 처리 오류: ${e.message}")
                    e.printStackTrace()
                }
            }
            
            // 서버 메시지 수신 (디버깅용)
            socket?.on("server_message") { args ->
                val data = args[0] as? JSONObject
                val msg = data?.optString("msg", "")
                Log.d(TAG, "📨 서버 메시지: $msg")
            }
            
            socket?.connect()
            
        } catch (e: URISyntaxException) {
            Log.e(TAG, "❌ Socket.IO URL 파싱 오류: ${e.message}")
            e.printStackTrace()
        } catch (e: Exception) {
            Log.e(TAG, "❌ Socket.IO 연결 실패: ${e.message}")
            e.printStackTrace()
        }
    }
    
    /**
     * 디바이스 등록
     */
    private fun registerDevice() {
        try {
            val data = JSONObject().apply {
                put("device", "mobile")
            }
            socket?.emit("register_device", data)
            Log.d(TAG, "📝 디바이스 등록: mobile")
        } catch (e: Exception) {
            Log.e(TAG, "❌ 디바이스 등록 실패: ${e.message}")
        }
    }
    
    /**
     * Clarify 입력 텍스트 전송
     * 
     * 사용자가 텍스트로 Clarify 응답을 입력할 때 사용합니다.
     * Socket.IO를 통해 FastAPI 서버로 전달됩니다.
     * 
     * @param text 사용자 입력 텍스트
     * @param sessionId Clarify 세션 ID
     * @param turnId 현재 Clarify 턴 ID
     * @param action "continue" | "skip" | "cancel"
     * @return 전송 성공 여부
     */
    fun sendClarifyTextResponse(
        text: String,
        sessionId: String,
        turnId: Int,
        action: String = "continue"
    ): Boolean {
        if (!isConnected()) {
            Log.w(TAG, "⚠️ Socket.IO 서버에 연결되어 있지 않습니다.")
            return false
        }
        
        return try {
            val payload = JSONObject().apply {
                put("text", text)
                put("session_id", sessionId)
                put("turn_id", turnId)
                put("action", action)
            }
            
            socket?.emit("clarify_input", payload)
            Log.i(TAG, "📤 Clarify 텍스트 응답 전송: session_id=$sessionId, turn_id=$turnId, text=$text")
            true
        } catch (e: Exception) {
            Log.e(TAG, "❌ Clarify 응답 전송 실패: ${e.message}")
            e.printStackTrace()
            false
        }
    }
    
    /**
     * Clarify 입력 텍스트 전송 (사용하지 않음)
     * 
     * 방식 1 구조에서는 모바일이 Clarify 입력을 전송하지 않습니다.
     * 라즈베리파이 Streaming STT가 FastAPI로 직접 전송되고,
     * FastAPI가 Socket.IO 서버로 clarify_response를 전송합니다.
     * 
     * @deprecated 이 메서드는 사용하지 않습니다. 방식 1에서는 Clarify 입력이 라즈베리파이 Streaming STT를 통해 전달됩니다.
     */
    @Deprecated("방식 1에서는 Clarify 입력이 라즈베리파이 Streaming STT를 통해 FastAPI로 직접 전송됩니다")
    fun sendClarifyInput(text: String, sessionId: String): Boolean {
        Log.w(TAG, "⚠️ sendClarifyInput은 사용하지 않습니다. 라즈베리파이 Streaming STT가 FastAPI로 직접 전송됩니다.")
        return false
    }
    
    /**
     * 연결 상태 확인
     */
    fun isConnected(): Boolean = isConnected && socket?.connected() == true
    
    /**
     * 연결 종료
     */
    fun disconnect() {
        try {
            socket?.disconnect()
            socket?.off()
            socket = null
            isConnected = false
            Log.i(TAG, "🛑 Socket.IO 연결 종료")
        } catch (e: Exception) {
            Log.e(TAG, "❌ 연결 종료 오류: ${e.message}")
        }
    }
    
    /**
     * 연결 상태 확인
     */
    fun isConnected(): Boolean = isConnected && socket?.connected() == true
    
    /**
     * 연결 종료
     */
    fun disconnect() {
        try {
            socket?.disconnect()
            socket?.off()
            socket = null
            isConnected = false
            Log.i(TAG, "🛑 Socket.IO 연결 종료")
        } catch (e: Exception) {
            Log.e(TAG, "❌ 연결 종료 오류: ${e.message}")
        }
    }
    
    /**
     * 라즈베리파이 제어 명령 전송
     * 모바일 → Socket.IO 서버 → 라즈베리파이로 제어 명령 전달
     * 
     * @param command 제어 명령 ("start_streaming_stt" | "set_stt_mode" | "notify_intent_done")
     * @param data 추가 데이터 (mode, branch 등)
     * @return 전송 성공 여부
     */
    fun sendRaspberryPiControl(command: String, data: Map<String, Any> = emptyMap()): Boolean {
        if (!isConnected()) {
            Log.w(TAG, "⚠️ Socket.IO 서버에 연결되어 있지 않습니다. 라즈베리파이 제어 명령을 전송할 수 없습니다.")
            return false
        }
        
        return try {
            val payload = JSONObject().apply {
                put("command", command)
                data.forEach { (key, value) ->
                    when (value) {
                        is String -> put(key, value)
                        is Int -> put(key, value)
                        is Boolean -> put(key, value)
                        is Double -> put(key, value)
                        else -> put(key, value.toString())
                    }
                }
            }
            
            socket?.emit("control_raspi", payload)
            Log.i(TAG, "📤 라즈베리파이 제어 명령 전송: command=$command")
            true
        } catch (e: Exception) {
            Log.e(TAG, "❌ 라즈베리파이 제어 명령 전송 실패: ${e.message}")
            e.printStackTrace()
            false
        }
    }
    
    /**
     * Ping 전송 (연결 테스트용)
     */
    fun ping() {
        try {
            val data = JSONObject().apply {
                put("message", "ping from mobile")
            }
            socket?.emit("ping", data)
            Log.d(TAG, "📡 Ping 전송")
        } catch (e: Exception) {
            Log.e(TAG, "❌ Ping 전송 실패: ${e.message}")
        }
    }
}

