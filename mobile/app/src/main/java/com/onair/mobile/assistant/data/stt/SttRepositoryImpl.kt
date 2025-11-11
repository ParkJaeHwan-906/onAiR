package com.onair.mobile.assistant.data.stt

import android.content.Context
import com.onair.mobile.assistant.core.common.Result
import com.onair.mobile.assistant.domain.repository.SttRepository

/**
 * STT 리포지토리 구현체
 * 
 * 라즈베리파이로부터 STT 텍스트를 수신하는 전용 Repository
 */
class SttRepositoryImpl(
    private val context: Context
) : SttRepository {
    
    // 라즈베리파이 텍스트 수신
    private val raspberryPiReceiver = RaspberryPiTextReceiver()
    
    /**
     * 라즈베리파이로부터 텍스트 수신
     */
    fun receiveFromRaspberryPi(text: String) {
        raspberryPiReceiver.receiveText(text)
    }
    
    /**
     * 라즈베리파이 텍스트 수신 상태 (Flow)
     */
    fun getRaspberryPiTextFlow() = raspberryPiReceiver.receivedText
    
    fun stop() {
        // 라즈베리파이 방식은 중지 불필요
    }
    
    fun cleanup() {
        raspberryPiReceiver.clear()
    }

    /**
     * 단일 오디오 파일 STT (비동기)
     * 
     * 라즈베리파이 방식에서는 사용하지 않음.
     * 라즈베리파이에서 STT 처리 후 텍스트만 전송하므로 이 메서드는 호환성 유지용.
     */
    override suspend fun transcribe(audioBytes: ByteArray): com.onair.mobile.assistant.core.common.Result<String> {
        return com.onair.mobile.assistant.core.common.Result.Error(
            Exception("라즈베리파이 방식에서는 이 메서드를 사용하지 않습니다. receiveFromRaspberryPi()를 사용하세요.")
        )
    }
}
