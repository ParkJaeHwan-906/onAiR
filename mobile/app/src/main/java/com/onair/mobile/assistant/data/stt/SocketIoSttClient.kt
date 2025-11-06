package com.onair.mobile.assistant.data.stt

import android.util.Log
import com.onair.mobile.assistant.core.model.dto.RagResponse
import com.onair.mobile.assistant.core.model.dto.EmbeddingResultDto
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
 * - "embedding_result": 버퍼링 STT 후 Phi-3 임베딩 수신 (Intent 분류용)
 * - "clarify_turn": Clarify 질문/답변 턴 수신
 * - "final_answer": 최종 답변 수신
 * - "clarify_response": Clarify 응답 (레거시, clarify_turn과 final_answer로 대체 예정)
 * 
 * 주의:
 * - Clarify 입력은 모바일에서 전송하지 않음
 * - 라즈베리파이 Streaming STT → FastAPI (직접) → FastAPI가 Socket.IO 서버로 clarify_turn/final_answer 전송
 */
class SocketIoSttClient(
    private val serverUrl: String,  // 예: "http://192.168.0.100:5000"
    private val onSttResult: (String, String, String?) -> Unit,  // (text, type, confidence)
    private val onClarifyResponse: ((RagResponse) -> Unit)? = null,  // Clarify 응답 콜백 (레거시)
    private val onEmbeddingResult: ((EmbeddingResultDto) -> Unit)? = null,  // 임베딩 결과 콜백
    private val onClarifyTurn: ((ClarifyTurnDto) -> Unit)? = null,  // Clarify 턴 콜백
    private val onFinalAnswer: ((FinalAnswerDto) -> Unit)? = null  // 최종 답변 콜백
) {
    private val TAG = "SocketIoSttClient"
    private var socket: Socket? = null
    private var isConnected = false
    private val gson = Gson()
    
    /**
     * Socket.IO 서버에 연결
     */
    fun connect() {
        try {
            val options = IO.Options().apply {
                reconnection = true
                reconnectionAttempts = 5
                reconnectionDelay = 1000
            }
            
            socket = IO.socket(serverUrl, options)
            
            // 연결 이벤트
            socket?.on(Socket.EVENT_CONNECT) {
                isConnected = true
                Log.i(TAG, "✅ Socket.IO 서버 연결 성공: $serverUrl")
                
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
            
            // embedding_result 이벤트 수신 (버퍼링 STT 후 Phi-3 임베딩)
            socket?.on("embedding_result") { args ->
                try {
                    val data = args[0] as? JSONObject
                    if (data != null) {
                        val jsonString = data.toString()
                        Log.d(TAG, "📩 임베딩 결과 수신: $jsonString")
                        
                        val embeddingResult = gson.fromJson(jsonString, EmbeddingResultDto::class.java)
                        onEmbeddingResult?.invoke(embeddingResult)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "❌ 임베딩 결과 처리 오류: ${e.message}")
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
     * FastAPI의 /api/clarify/response 엔드포인트로 HTTP POST 요청을 보냅니다.
     * 
     * @param text 사용자 입력 텍스트
     * @param sessionId Clarify 세션 ID
     * @param turnId 현재 Clarify 턴 ID
     * @param action "continue" | "skip" | "cancel"
     * @param fastApiUrl FastAPI 서버 URL (예: "http://192.168.0.100:8000")
     * @return 전송 성공 여부
     */
    fun sendClarifyTextResponse(
        text: String,
        sessionId: String,
        turnId: Int,
        action: String = "continue",
        fastApiUrl: String
    ): Boolean {
        // HTTP POST로 FastAPI에 직접 전송 (ai_ar 폴더 수정 불가로 인해 직접 전송)
        return try {
            val client = okhttp3.OkHttpClient()
            val json = JSONObject().apply {
                put("session_id", sessionId)
                put("turn_id", turnId)
                put("response", text)
                put("action", action)
            }
            
            val requestBody = okhttp3.RequestBody.create(
                okhttp3.MediaType.parse("application/json; charset=utf-8"),
                json.toString()
            )
            
            val request = okhttp3.Request.Builder()
                .url("$fastApiUrl/api/clarify/response")
                .post(requestBody)
                .build()
            
            val response = client.newCall(request).execute()
            val success = response.isSuccessful
            
            if (success) {
                Log.i(TAG, "📤 Clarify 텍스트 응답 전송 완료: session_id=$sessionId, turn_id=$turnId, text=$text")
            } else {
                Log.e(TAG, "❌ Clarify 응답 전송 실패: HTTP ${response.code()}")
            }
            
            response.close()
            success
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

