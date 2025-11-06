package com.onair.mobile.assistant.data.stt

import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * 라즈베리파이로부터 받은 텍스트 수신용
 * 
 * 라즈베리파이: 마이크 → VAD → STT → 텍스트 전송
 * 모바일: 텍스트 수신 → Intent 분기
 */
class RaspberryPiTextReceiver {

    private val TAG = "RaspberryPiTextReceiver"
    
    // 수신된 텍스트를 Flow로 제공 (실시간 업데이트)
    private val _receivedText = MutableStateFlow<String>("")
    val receivedText: StateFlow<String> = _receivedText
    
    /**
     * 라즈베리파이로부터 텍스트 수신
     * 
     * @param text 라즈베리파이에서 STT 처리된 텍스트
     */
    fun receiveText(text: String) {
        if (text.isNotBlank()) {
            Log.i(TAG, "✅ 라즈베리파이로부터 텍스트 수신: $text")
            _receivedText.value = text
        }
    }
    
    /**
     * 텍스트 초기화
     */
    fun clear() {
        _receivedText.value = ""
    }
}

