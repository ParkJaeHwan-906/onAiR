package com.onair.mobile.assistant.data.raspberry

import android.util.Log
import com.onair.mobile.assistant.core.model.dto.IntentDoneRequest
import com.onair.mobile.assistant.core.model.dto.SttModeRequest
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.POST

/**
 * 라즈베리파이 FastAPI 서버의 제어 API 인터페이스
 * 
 * 라즈베리파이 서버 URL: http://라즈베리파이_IP:PORT
 */
interface RaspberryPiControlApi {
    /**
     * STT 모드 설정
     * 
     * @param request 모드 설정 요청 {"mode": "buffered" | "streaming"}
     */
    @POST("/api/stt/mode")
    suspend fun setSttMode(@Body request: SttModeRequest): Response<Unit>
    
    /**
     * Intent 분기 완료 알림
     * 
     * @param request Intent 분기 정보 {"branch": "AI_SUPPORTER" | "OPERATOR"}
     */
    @POST("/api/stt/intent_done")
    suspend fun notifyIntentDone(@Body request: IntentDoneRequest): Response<Unit>
}

