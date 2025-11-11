package com.onair.mobile.assistant.data.raspberry

import android.util.Log
import com.onair.mobile.assistant.data.stt.SocketIoSttClient

/**
 * 라즈베리파이 제어 API Repository 구현체
 * 
 * Socket.IO를 통해 라즈베리파이에 제어 시그널을 전송합니다.
 * 모바일 → Socket.IO 서버 → 라즈베리파이
 */
class RaspberryPiControlRepository(
    private val socketIoSttClient: SocketIoSttClient
) {
    private val TAG = "RaspberryPiControl"
    
    /**
     * STT 모드 설정
     * 
     * @param mode "buffered" 또는 "streaming"
     */
    suspend fun setSttMode(mode: String): Boolean {
        return try {
            Log.d(TAG, "📡 STT 모드 설정 요청: mode=$mode")
            
            val success = socketIoSttClient.sendRaspberryPiControl(
                command = "set_stt_mode",
                data = mapOf("mode" to mode)
            )
            
            if (success) {
                Log.i(TAG, "✅ STT 모드 설정 성공: $mode")
            } else {
                Log.e(TAG, "❌ STT 모드 설정 실패")
            }
            success
        } catch (e: Exception) {
            Log.e(TAG, "❌ STT 모드 설정 오류: ${e.message}")
            e.printStackTrace()
            false
        }
    }
    
    /**
     * Intent 분기 완료 알림
     * 
     * @param branch "AI_SUPPORTER" 또는 "OPERATOR"
     */
    suspend fun notifyIntentDone(branch: String): Boolean {
        return try {
            Log.d(TAG, "📡 Intent 분기 완료 알림: branch=$branch")
            
            val success = socketIoSttClient.sendRaspberryPiControl(
                command = "notify_intent_done",
                data = mapOf("branch" to branch)
            )
            
            if (success) {
                Log.i(TAG, "✅ Intent 분기 완료 알림 성공: $branch")
            } else {
                Log.e(TAG, "❌ Intent 분기 완료 알림 실패")
            }
            success
        } catch (e: Exception) {
            Log.e(TAG, "❌ Intent 분기 완료 알림 오류: ${e.message}")
            e.printStackTrace()
            false
        }
    }
    
    /**
     * 스트리밍 STT 시작 명령
     */
    suspend fun startStreamingStt(): Boolean {
        return try {
            Log.d(TAG, "📡 스트리밍 STT 시작 명령")
            
            val success = socketIoSttClient.sendRaspberryPiControl(
                command = "start_streaming_stt"
            )
            
            if (success) {
                Log.i(TAG, "✅ 스트리밍 STT 시작 명령 성공")
            } else {
                Log.e(TAG, "❌ 스트리밍 STT 시작 명령 실패")
            }
            success
        } catch (e: Exception) {
            Log.e(TAG, "❌ 스트리밍 STT 시작 명령 오류: ${e.message}")
            e.printStackTrace()
            false
        }
    }
}

