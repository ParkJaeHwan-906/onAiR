package com.onair.mobile.assistant.data.stt

import android.util.Log
import com.onair.mobile.assistant.core.model.dto.RagResponse
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
 * - "clarify_response": Clarify 응답 (FastAPI에서 생성된 Gemini/GPT 응답)
 * 
 * 주의:
 * - Clarify 입력은 모바일에서 전송하지 않음
 * - 라즈베리파이 Streaming STT → FastAPI (직접) → FastAPI가 Socket.IO 서버로 clarify_response 전송
 */
class SocketIoSttClient(
    private val serverUrl: String,  // 예: "http://192.168.0.100:5000"
    private val onSttResult: (String, String, String?) -> Unit,  // (text, type, confidence)
    private val onClarifyResponse: ((RagResponse) -> Unit)? = null  // Clarify 응답 콜백 (선택사항)
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
            
            // clarify_response 이벤트 수신 (Clarify 응답)
            socket?.on("clarify_response") { args ->
                try {
                    val data = args[0] as? JSONObject
                    if (data != null) {
                        val jsonString = data.toString()
                        Log.d(TAG, "📩 Clarify 응답 수신: $jsonString")
                        
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

