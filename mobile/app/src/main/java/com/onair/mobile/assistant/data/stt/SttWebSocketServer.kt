package com.onair.mobile.assistant.data.stt

import android.util.Log
import org.java_websocket.WebSocket
import org.java_websocket.handshake.ClientHandshake
import org.java_websocket.server.WebSocketServer
import java.net.InetSocketAddress

/**
 * 라즈베리파이로부터 STT 텍스트를 수신하는 WebSocket 서버
 * 
 * 라즈베리파이는 클라이언트로 ws://<안드로이드_IP>:8080/ws/stt 에 연결
 * 전송 형식: { "timestamp": "...", "text": "..." }
 */
class SttWebSocketServer(
    port: Int,
    private val onSttMessage: (String, String) -> Unit  // (timestamp, text)
) : WebSocketServer(InetSocketAddress(port)) {

    private val TAG = "SttWebSocketServer"
    private val serverPort = port

    override fun onOpen(conn: WebSocket, handshake: ClientHandshake) {
        Log.i(TAG, "✅ 라즈베리파이 연결됨: ${conn.remoteSocketAddress}")
    }

    override fun onMessage(conn: WebSocket, message: String) {
        Log.d(TAG, "📩 STT 텍스트 수신: $message")
        
        try {
            // JSON 파싱
            val json = org.json.JSONObject(message)
            val text = json.getString("text")
            val timestamp = json.optString("timestamp", System.currentTimeMillis().toString())
            
            if (text.isNotBlank()) {
                Log.i(TAG, "🧠 STT 처리: [$timestamp] $text")
                onSttMessage(timestamp, text)
            } else {
                Log.w(TAG, "⚠️ 빈 텍스트 수신")
            }
        } catch (e: org.json.JSONException) {
            Log.e(TAG, "❌ JSON 파싱 오류: ${e.message}")
            Log.e(TAG, "수신된 메시지: $message")
        } catch (e: Exception) {
            Log.e(TAG, "❌ 메시지 처리 오류: ${e.message}")
            e.printStackTrace()
        }
    }

    override fun onClose(conn: WebSocket, code: Int, reason: String, remote: Boolean) {
        Log.i(TAG, "🔌 라즈베리파이 연결 종료: $reason (code: $code)")
    }

    override fun onError(conn: WebSocket?, ex: Exception) {
        Log.e(TAG, "❌ WebSocket 오류: ${ex.message}")
        ex.printStackTrace()
    }

    override fun onStart() {
        Log.i(TAG, "🚀 WebSocket 서버 시작: ws://0.0.0.0:$serverPort/ws/stt")
    }
    
    /**
     * 서버 중지
     */
    fun stopServer() {
        try {
            stop()
            Log.i(TAG, "🛑 WebSocket 서버 중지됨")
        } catch (e: Exception) {
            Log.e(TAG, "❌ 서버 중지 오류: ${e.message}")
        }
    }
}

