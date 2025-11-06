package com.onair.mobile.assistant.data.stt

import android.util.Log
import fi.iki.elonen.NanoHTTPD
import org.json.JSONObject
import java.io.IOException

/**
 * 라즈베리파이로부터 stt_start 웹훅 알림을 수신하는 HTTP 서버
 * 
 * 라즈베리파이는 POST http://<안드로이드_IP>:8081/webhook/stt_start 로 알림 전송
 * 요청 본문: { "event": "stt_start" }
 */
class SttWebhookServer(
    port: Int,
    private val onSttStart: () -> Unit
) : NanoHTTPD(port) {

    private val TAG = "SttWebhookServer"
    private val serverPort = port

    override fun serve(session: IHTTPSession): Response {
        val method = session.method
        val uri = session.uri

        Log.d(TAG, "📥 HTTP 요청: $method $uri")

        // POST /webhook/stt_start 엔드포인트 처리
        if (method == Method.POST && uri == "/webhook/stt_start") {
            return handleSttStart(session)
        }

        // 404 Not Found
        return newFixedLengthResponse(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "Not Found")
    }

    /**
     * stt_start 웹훅 처리
     */
    private fun handleSttStart(session: IHTTPSession): Response {
        try {
            // POST 본문 읽기
            val contentLength = session.headers["content-length"]?.toIntOrNull() ?: 0
            val buffer = ByteArray(contentLength)
            session.inputStream.read(buffer, 0, contentLength)
            val body = String(buffer)

            Log.d(TAG, "📩 웹훅 본문: $body")

            // JSON 파싱
            val json = JSONObject(body)
            val event = json.optString("event", "")

            if (event == "stt_start") {
                Log.i(TAG, "✅ STT 시작 알림 수신")
                onSttStart()
                
                // 성공 응답
                return newFixedLengthResponse(
                    Response.Status.OK,
                    "application/json",
                    """{"status": "ok", "message": "STT start notification received"}"""
                )
            } else {
                Log.w(TAG, "⚠️ 알 수 없는 이벤트: $event")
                return newFixedLengthResponse(
                    Response.Status.BAD_REQUEST,
                    "application/json",
                    """{"status": "error", "message": "Unknown event: $event"}"""
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ 웹훅 처리 오류: ${e.message}")
            e.printStackTrace()
            return newFixedLengthResponse(
                Response.Status.INTERNAL_ERROR,
                "application/json",
                """{"status": "error", "message": "${e.message}"}"""
            )
        }
    }

    /**
     * 서버 시작
     */
    fun startServer() {
        try {
            start(NanoHTTPD.SOCKET_READ_TIMEOUT, false)
            Log.i(TAG, "🚀 HTTP 웹훅 서버 시작: http://0.0.0.0:$serverPort/webhook/stt_start")
        } catch (e: IOException) {
            Log.e(TAG, "❌ HTTP 서버 시작 실패: ${e.message}")
            e.printStackTrace()
        }
    }

    /**
     * 서버 중지
     */
    fun stopServer() {
        try {
            stop()
            Log.i(TAG, "🛑 HTTP 웹훅 서버 중지됨")
        } catch (e: Exception) {
            Log.e(TAG, "❌ 서버 중지 오류: ${e.message}")
        }
    }
}

