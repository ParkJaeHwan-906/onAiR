package com.onair.mobile

import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.onair.mobile.assistant.data.intent.IntentRepositoryImpl
import com.onair.mobile.assistant.data.stt.SttRepositoryImpl
import com.onair.mobile.assistant.data.stt.SttWebSocketServer
import com.onair.mobile.assistant.domain.usecase.ClassifyIntentUseCase
import com.onair.mobile.assistant.domain.usecase.DispatchIntentUseCase
import com.onair.mobile.assistant.domain.usecase.DispatchResult
import kotlinx.coroutines.launch

/**
 * 라즈베리파이로부터 STT 텍스트를 수신하는 WebSocket 서버 Activity
 * 
 * 실행 방법:
 * 1. Android Studio에서 Run
 * 2. 로그에서 "🚀 WebSocket 서버 시작" 확인
 * 3. 라즈베리파이에서 ws://<안드로이드_IP>:8080/ws/stt 연결
 */
class MainActivitySttServer : AppCompatActivity() {

    private lateinit var server: SttWebSocketServer
    private lateinit var sttRepository: SttRepositoryImpl
    private lateinit var intentRepository: IntentRepositoryImpl
    private lateinit var classifyIntentUseCase: ClassifyIntentUseCase
    private lateinit var dispatchIntentUseCase: DispatchIntentUseCase
    
    private val TAG = "MainActivitySttServer"
    private val WS_PORT = 8080

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)  // 기본 레이아웃 사용
        
        // STT Repository 초기화
        sttRepository = SttRepositoryImpl(this)
        
        // Intent Classifier 초기화
        intentRepository = IntentRepositoryImpl(this)
        classifyIntentUseCase = ClassifyIntentUseCase(intentRepository)
        
        // Intent Dispatcher 초기화
        // TODO: CV API, Clarification API, LLM API가 준비되면 주입
        dispatchIntentUseCase = DispatchIntentUseCase(
            detectObjectUseCase = null,  // TODO: DetectObjectUseCase 주입
            clarifyQuestionUseCase = null,  // TODO: ClarifyQuestionUseCase 주입
            llmRepository = null  // TODO: LlmRepositoryImpl 주입
        )
        
        // WebSocket 서버 시작
        server = SttWebSocketServer(WS_PORT) { timestamp, text ->
            handleSttMessage(timestamp, text)
        }
        
        try {
            server.start()
            Log.i(TAG, "✅ STT WebSocket 서버 시작: ws://0.0.0.0:$WS_PORT/ws/stt")
            Log.i(TAG, "📱 안드로이드 기기 IP를 확인하여 라즈베리파이에서 연결하세요")
        } catch (e: Exception) {
            Log.e(TAG, "❌ WebSocket 서버 시작 실패: ${e.message}")
            e.printStackTrace()
        }
    }

    private fun handleSttMessage(timestamp: String, text: String) {
        Log.i(TAG, "🧠 STT 텍스트 처리: [$timestamp] $text")
        
        // SttRepository를 통해 텍스트 수신
        sttRepository.receiveFromRaspberryPi(text)
        
        // Intent Classifier → Intent Dispatcher 호출
        lifecycleScope.launch {
            try {
                // 1. Intent 분류
                val intentResult = classifyIntentUseCase(text)
                Log.i(TAG, "✅ Intent 분류 완료: ${intentResult.intentType.value} (신뢰도: ${intentResult.confidence})")
                
                // 2. Intent 분기 처리
                val dispatchResult = dispatchIntentUseCase(intentResult)
                
                // 3. 결과 처리
                handleDispatchResult(dispatchResult)
            } catch (e: Exception) {
                Log.e(TAG, "❌ Intent 처리 실패: ${e.message}")
                e.printStackTrace()
            }
        }
        
        // UI 업데이트 (필요 시)
        runOnUiThread {
            // TextView 등에 텍스트 표시
            // textView.text = text
        }
    }
    
    /**
     * Intent 분기 처리 결과를 받아서 최종 처리
     */
    private fun handleDispatchResult(dispatchResult: DispatchResult) {
        when (dispatchResult) {
            is DispatchResult.Success -> {
                when (dispatchResult.type) {
                    com.onair.mobile.assistant.domain.entity.IntentType.OPERATOR -> {
                        Log.i(TAG, "✅ Operator 처리 완료: ${dispatchResult.message}")
                        // TODO: RTC 연결 상태 UI 업데이트
                    }
                    com.onair.mobile.assistant.domain.entity.IntentType.AI_SUPPORTER -> {
                        Log.i(TAG, "✅ AI Supporter 처리 완료: ${dispatchResult.message}")
                        // TODO: Vision Analyzer 결과 또는 LLM 응답 처리
                        // TODO: TTS로 응답 전송
                    }
                    else -> {}
                }
            }
            is DispatchResult.Error -> {
                Log.e(TAG, "❌ Intent 처리 오류: ${dispatchResult.message}")
                // TODO: 에러 처리 로직
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        server.stopServer()
        sttRepository.cleanup()
        intentRepository.cleanup()
        Log.i(TAG, "🛑 WebSocket 서버 중지됨")
    }
}

