package com.onair.mobile.assistant.data.webrtc

import com.onair.mobile.assistant.core.model.dto.WebRtcRequestDto
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.POST

/**
 * Spring 서버 WebRTC API 인터페이스
 */
interface WebRtcApi {
    /**
     * WebRTC 연결 요청
     * 
     * @param authorization Bearer 토큰
     * @param request WebRTC 요청 DTO
     */
    @POST("webrtc/request")  // 상대 경로 (앞의 / 제거하여 baseUrl과 결합되도록)
    suspend fun requestConnection(
        @Header("Authorization") authorization: String,
        @Body request: WebRtcRequestDto
    ): Response<Unit>
}

