package com.onair.mobile

import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.onair.mobile.assistant.core.common.SessionManager
import com.onair.mobile.assistant.data.intent.EmbeddingRepository
import com.onair.mobile.assistant.data.intent.IntentRepositoryImpl
import com.onair.mobile.assistant.data.llm.LlmRepositoryImpl
import com.onair.mobile.assistant.data.rag.RagRepositoryImpl
import com.onair.mobile.assistant.data.raspberry.RaspberryPiControlRepository
import com.onair.mobile.assistant.data.stt.SocketIoSttClient
import com.onair.mobile.assistant.data.stt.SttRepositoryImpl
import com.onair.mobile.assistant.data.stt.SttWebhookServer
import com.onair.mobile.assistant.data.stt.SttWebSocketServer
import com.onair.mobile.assistant.data.tts.MediaPlayerController
import com.onair.mobile.assistant.data.tts.TtsRepositoryImpl
import com.onair.mobile.assistant.domain.entity.IntentType
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
 * 4. 라즈베리파이에서 POST http://<안드로이드_IP>:8081/webhook/stt_start 알림 전송
 */
class MainActivitySttServer : AppCompatActivity() {

    private lateinit var socketIoSttClient: SocketIoSttClient
    private lateinit var webSocketServer: SttWebSocketServer  // 레거시, Socket.IO로 대체 예정
    private lateinit var webhookServer: SttWebhookServer
    private lateinit var sttRepository: SttRepositoryImpl
    private lateinit var intentRepository: IntentRepositoryImpl
    private lateinit var classifyIntentUseCase: ClassifyIntentUseCase
    private lateinit var dispatchIntentUseCase: DispatchIntentUseCase
    private lateinit var sessionManager: SessionManager
    private lateinit var llmRepository: LlmRepositoryImpl
    private lateinit var ttsRepository: TtsRepositoryImpl
    private lateinit var mediaPlayerController: MediaPlayerController
    private lateinit var raspberryPiControlRepository: RaspberryPiControlRepository
    
    private var isWaitingForClarification = false
    private var currentSessionId: String? = null
    
    private val TAG = "MainActivitySttServer"
    private val WS_PORT = 8080  // WebSocket 서버 포트 (레거시)
    private val WEBHOOK_PORT = 8081  // HTTP 웹훅 서버 포트
    
    // TODO: 서버 URL 설정
    private val SOCKET_IO_SERVER_URL = "http://YOUR_SOCKET_IO_SERVER_URL:5000"  // Socket.IO 서버 URL
    private val FASTAPI_SERVER_URL = "http://YOUR_FASTAPI_SERVER_URL:8000"  // FastAPI 서버 URL
    private val RASPBERRY_PI_SERVER_URL = "http://YOUR_RASPBERRY_PI_URL:5000"  // 라즈베리파이 FastAPI 서버 URL

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)  // 기본 레이아웃 사용
        
        // STT Repository 초기화
        sttRepository = SttRepositoryImpl(this)
        
        // Embedding Repository 초기화
        val embeddingRepository = EmbeddingRepository(baseUrl = FASTAPI_SERVER_URL)
        
        // Intent Classifier 초기화
        intentRepository = IntentRepositoryImpl(this, embeddingRepository)
        classifyIntentUseCase = ClassifyIntentUseCase(intentRepository)
        
        // 세션 관리자 초기화
        sessionManager = SessionManager()
        
        // RAG Repository 초기화
        val ragRepository = RagRepositoryImpl(FASTAPI_SERVER_URL)
        llmRepository = LlmRepositoryImpl(ragRepository)
        
        // MediaPlayer Controller 초기화
        mediaPlayerController = MediaPlayerController(this)
        
        // TTS Repository 초기화
        ttsRepository = TtsRepositoryImpl(this, mediaPlayerController)
        
        // 라즈베리파이 제어 API 초기화
        raspberryPiControlRepository = RaspberryPiControlRepository(RASPBERRY_PI_SERVER_URL)
        
        // Intent Dispatcher 초기화
        dispatchIntentUseCase = DispatchIntentUseCase(
            detectObjectUseCase = null,  // CV API는 선택사항
            llmRepository = llmRepository,
            sessionManager = sessionManager
        )
        
        // Socket.IO 클라이언트 시작 (Socket.IO 서버에서 stt_result 및 clarify_response 이벤트 수신)
        socketIoSttClient = SocketIoSttClient(
            serverUrl = SOCKET_IO_SERVER_URL,
            onSttResult = { text, type, confidence ->
                val timestamp = System.currentTimeMillis().toString()
                handleSttMessage(timestamp, text)
            },
            onClarifyResponse = { ragResponse ->
                // Clarify 응답 수신 처리
                handleClarifyResponseFromSocket(ragResponse)
            }
        )
        
        try {
            socketIoSttClient.connect()
            Log.i(TAG, "✅ Socket.IO 클라이언트 연결 시작: $SOCKET_IO_SERVER_URL")
        } catch (e: Exception) {
            Log.e(TAG, "❌ Socket.IO 클라이언트 연결 실패: ${e.message}")
            e.printStackTrace()
        }
        
        // 레거시 WebSocket 서버 (선택사항, Socket.IO로 대체 예정)
        webSocketServer = SttWebSocketServer(WS_PORT) { timestamp, text ->
            handleSttMessage(timestamp, text)
        }
        
        try {
            webSocketServer.start()
            Log.i(TAG, "✅ 레거시 WebSocket 서버 시작: ws://0.0.0.0:$WS_PORT/ws/stt")
        } catch (e: Exception) {
            Log.e(TAG, "❌ 레거시 WebSocket 서버 시작 실패: ${e.message}")
            e.printStackTrace()
        }
        
        // HTTP 웹훅 서버 시작 (stt_start 알림 수신용)
        webhookServer = SttWebhookServer(WEBHOOK_PORT) {
            handleSttStart()
        }
        
        try {
            webhookServer.startServer()
            Log.i(TAG, "✅ HTTP 웹훅 서버 시작: http://0.0.0.0:$WEBHOOK_PORT/webhook/stt_start")
            Log.i(TAG, "📱 안드로이드 기기 IP를 확인하여 라즈베리파이에서 연결하세요")
        } catch (e: Exception) {
            Log.e(TAG, "❌ HTTP 웹훅 서버 시작 실패: ${e.message}")
            e.printStackTrace()
        }
    }

    /**
     * 라즈베리파이에서 stt_start 웹훅 알림 수신 시 호출
     */
    private fun handleSttStart() {
        Log.i(TAG, "🎙️ STT 시작 알림 수신 - 라즈베리파이에서 음성 수집 시작")
        // TODO: 필요 시 UI 업데이트 (예: "듣고 있습니다..." 표시)
    }
    
    /**
     * 라즈베리파이로부터 STT 텍스트 수신 시 호출
     * 
     * 버퍼링 STT: Intent 분류 수행
     * Streaming STT: Clarify 입력이지만, 모바일에서 처리하지 않음
     *                (라즈베리파이 → FastAPI 직접 전송 → FastAPI가 Socket.IO로 clarify_response 전송)
     */
    private fun handleSttMessage(timestamp: String, text: String) {
        Log.i(TAG, "🧠 STT 텍스트 처리: [$timestamp] $text")
        
        // SttRepository를 통해 텍스트 수신
        sttRepository.receiveFromRaspberryPi(text)
        
        if (isWaitingForClarification) {
            // Clarify 진행 중: Streaming STT는 FastAPI로 직접 전송되므로 모바일에서 처리하지 않음
            // FastAPI가 처리 후 Socket.IO 서버로 clarify_response를 전송하면
            // Socket.IO 클라이언트의 onClarifyResponse 콜백으로 수신됨
            Log.d(TAG, "💬 Clarify 진행 중 - Streaming STT는 FastAPI로 직접 전송됨")
        } else {
            // 일반 질문: Intent 분류 수행 (버퍼링 STT)
            handleNormalQuestion(text)
        }
    }
    
    /**
     * 일반 질문 처리 (최초 질문)
     */
    private fun handleNormalQuestion(text: String) {
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
    }
    
    /**
     * Clarify 입력 처리
     * 
     * 방식 1 구조에서는 모바일이 Clarify 입력을 전송하지 않습니다.
     * 라즈베리파이 Streaming STT가 FastAPI로 직접 전송되고,
     * FastAPI가 처리한 후 Socket.IO 서버로 clarify_response를 전송합니다.
     * 
     * 이 메서드는 호출되지 않습니다 (Clarify 입력은 라즈베리파이 Streaming STT를 통해 처리됨).
     */
    private fun handleClarificationInput(text: String) {
        Log.w(TAG, "⚠️ handleClarificationInput은 호출되지 않아야 합니다. 라즈베리파이 Streaming STT가 FastAPI로 직접 전송됩니다.")
        // Clarify 입력은 라즈베리파이 Streaming STT를 통해 FastAPI로 직접 전송되므로
        // 모바일에서는 처리하지 않음
        // FastAPI가 처리 후 Socket.IO 서버로 clarify_response를 전송하면
        // Socket.IO 클라이언트의 onClarifyResponse 콜백으로 수신됨
    }
    
    /**
     * Intent 분기 처리 결과를 받아서 최종 처리
     */
    private fun handleDispatchResult(dispatchResult: DispatchResult) {
        when (dispatchResult) {
            is DispatchResult.Success -> {
                when (dispatchResult.type) {
                    IntentType.OPERATOR -> {
                        Log.i(TAG, "✅ Operator 처리 완료: ${dispatchResult.message}")
                        
                        // 라즈베리파이 제어: 마이크 resume + 모드 buffered 유지
                        lifecycleScope.launch {
                            raspberryPiControlRepository.notifyIntentDone("OPERATOR")
                        }
                        
                        // TODO: RTC 연결 상태 UI 업데이트
                    }
                    IntentType.AI_SUPPORTER -> {
                        // 라즈베리파이 제어: Streaming STT 모드로 전환 + 마이크 resume
                        lifecycleScope.launch {
                            raspberryPiControlRepository.setSttMode("streaming")
                            raspberryPiControlRepository.notifyIntentDone("AI_SUPPORTER")
                        }
                        
                        if (dispatchResult.isClarifyNeeded) {
                            // Clarify 응답 → 사용자 입력 대기
                            val sessionId = sessionManager.getOrCreateSessionId()
                            
                            handleClarifyResponse(dispatchResult.data, dispatchResult.options)
                            isWaitingForClarification = true
                            currentSessionId = sessionId
                        } else {
                            // 최종 답변 → 오디오 재생
                            handleFinalAnswer(dispatchResult.data, dispatchResult.audioContent, dispatchResult.mimeType)
                            isWaitingForClarification = false
                            sessionManager.resetSession()
                            currentSessionId = null
                        }
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
    
    /**
     * Socket.IO로부터 Clarify 응답 수신 처리
     */
    private fun handleClarifyResponseFromSocket(ragResponse: com.onair.mobile.assistant.core.model.dto.RagResponse) {
        if (ragResponse.need_clarify == true) {
            // 아직 Clarify 필요
            val clarifyGuidance = ragResponse.clarify_guidance ?: ragResponse.ask ?: ""
            handleClarifyResponse(clarifyGuidance, ragResponse.options)
            // isWaitingForClarification은 이미 true 상태 유지
        } else {
            // 최종 답변 도착
            handleFinalAnswer(ragResponse)
            isWaitingForClarification = false
            sessionManager.resetSession()
            currentSessionId = null
        }
    }
    
    /**
     * Clarify 응답 처리
     */
    private fun handleClarifyResponse(guidance: String, options: List<String>? = null) {
        Log.i(TAG, "💬 Clarify 질문: $guidance")
        if (options != null && options.isNotEmpty()) {
            Log.i(TAG, "📋 Clarify 옵션: ${options.joinToString(", ")}")
        }
        // TODO: UI에 Clarify 질문 표시
    }
    
    /**
     * 최종 답변 처리
     */
    private fun handleFinalAnswer(answer: String, audioContent: String? = null, mimeType: String? = null) {
        Log.i(TAG, "✅ 최종 답변: $answer")
        
        // 오디오 재생
        if (audioContent != null && audioContent.isNotBlank()) {
            lifecycleScope.launch {
                ttsRepository.playAudio(audioContent, mimeType)
            }
        } else {
            Log.w(TAG, "⚠️ 오디오 파일이 포함되지 않음")
        }
        
        // TODO: UI에 답변 표시
    }
    
    /**
     * 최종 답변 처리 (RagResponse 직접 사용)
     */
    private suspend fun handleFinalAnswer(ragResponse: com.onair.mobile.assistant.core.model.dto.RagResponse) {
        val answer = ragResponse.result?.answer ?: ""
        val audioContent = ragResponse.result?.audio_content
        val mimeType = ragResponse.result?.mime_type
        
        handleFinalAnswer(answer, audioContent, mimeType)
    }

    override fun onDestroy() {
        super.onDestroy()
        socketIoSttClient.disconnect()
        webSocketServer.stopServer()
        webhookServer.stopServer()
        sttRepository.cleanup()
        intentRepository.cleanup()
        ttsRepository.cleanup()
        Log.i(TAG, "🛑 서버 중지됨")
    }
}

