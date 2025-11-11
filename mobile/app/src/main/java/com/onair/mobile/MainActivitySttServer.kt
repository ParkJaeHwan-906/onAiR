package com.onair.mobile

import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import com.onair.mobile.assistant.core.common.SessionManager
import com.onair.mobile.assistant.data.intent.IntentRepositoryImpl
import com.onair.mobile.assistant.data.llm.LlmRepositoryImpl
import com.onair.mobile.assistant.data.rag.RagRepositoryImpl
import com.onair.mobile.assistant.data.raspberry.RaspberryPiControlRepository
import com.onair.mobile.assistant.data.stt.SocketIoSttClient
import com.onair.mobile.assistant.data.stt.SttRepositoryImpl
import com.onair.mobile.assistant.data.tts.MediaPlayerController
import com.onair.mobile.assistant.data.tts.TtsRepositoryImpl
import com.onair.mobile.assistant.domain.entity.IntentType
import com.onair.mobile.assistant.core.model.dto.IntentResultDto
import com.onair.mobile.assistant.core.model.dto.ClarifyTurnDto
import com.onair.mobile.assistant.core.model.dto.FinalAnswerDto
import com.onair.mobile.assistant.core.model.dto.CvDetectionFailedDto
import com.onair.mobile.assistant.core.model.dto.ClarifyQaTurnDto
import com.onair.mobile.assistant.data.auth.TokenManager
import com.onair.mobile.assistant.data.webrtc.WebRtcRepository
import com.onair.mobile.assistant.data.task.SseTaskClient
import com.onair.mobile.communicate.PreferenceUtil
import com.onair.mobile.communicate.data.AuthRepository
import com.onair.mobile.communicate.data.api.ApiClient
import com.onair.mobile.communicate.data.api.ApiService
import com.onair.mobile.communicate.presentation.ui.LoginActivity
import android.content.Intent

/**
 * Socket.IO를 통해 라즈베리파이로부터 STT 텍스트를 수신하는 Activity
 * 
 * 실행 방법:
 * 1. Android Studio에서 Run
 * 2. 로그에서 "✅ Socket.IO 클라이언트 연결 시작" 확인
 * 3. 라즈베리파이는 Socket.IO 서버를 통해 STT 결과를 전송
 */
class MainActivitySttServer : AppCompatActivity() {

    private lateinit var socketIoSttClient: SocketIoSttClient
    private lateinit var sttRepository: SttRepositoryImpl
    private lateinit var intentRepository: IntentRepositoryImpl
    private lateinit var sessionManager: SessionManager
    private lateinit var llmRepository: LlmRepositoryImpl
    private lateinit var ttsRepository: TtsRepositoryImpl
    private lateinit var mediaPlayerController: MediaPlayerController
    private lateinit var raspberryPiControlRepository: RaspberryPiControlRepository
    private var sseTaskClient: SseTaskClient? = null
    private lateinit var tokenManager: TokenManager
    private lateinit var webRtcRepository: WebRtcRepository
    private lateinit var authRepository: AuthRepository
    private lateinit var preferenceUtil: PreferenceUtil
    
    private var isWaitingForClarification = false
    private var currentSessionId: String? = null
    private var currentTurnId: Int = 1  // Clarify 턴 ID 추적
    
    private val TAG = "MainActivitySttServer"
    
    // Wakeword 감지 시 재생할 음성 파일명 (assets 폴더에 있는 파일)
    companion object {
        private const val WAKEWORD_AUDIO_FILE = "001_onAir_서비스를_시작합니다_어떤_것을_도와드릴까요.mp3"
        private const val AI_SUPPORTER_AUDIO_FILE = "001_AI_Supporter_기능을_시작합니다_오류_탐지.mp3"
    }
    
    // 서버 URL 설정
    // EC2에 배포된 FastAPI 서버 URL (라즈베리파이와 동일한 URL 사용)
    private val FASTAPI_SERVER_URL = "https://onair.ai.kr"  // FastAPI 서버 URL (Socket.IO 경로: /ws)
    private val SPRING_SERVER_URL = "https://onair.ai.kr/api"  // Spring 서버 URL (SSE 엔드포인트)
    // ACCESS_TOKEN은 TokenManager를 통해 동적으로 불러옵니다

    // 테스트용 UI 참조
    private lateinit var statusText: android.widget.TextView
    private lateinit var intentText: android.widget.TextView
    private lateinit var clarifyText: android.widget.TextView
    private lateinit var finalAnswerText: android.widget.TextView
    private lateinit var logText: android.widget.TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // 로그인 상태 확인 (communication 폴더의 AuthRepository 사용)
        preferenceUtil = PreferenceUtil(applicationContext)
        val apiService = ApiClient(this).getRetrofit().create(ApiService::class.java)
        authRepository = AuthRepository(apiService, preferenceUtil)
        
        // 로그인 상태 확인
        val refreshToken = authRepository.getRefreshToken()
        if (refreshToken.isEmpty()) {
            // 로그인되지 않음 → LoginActivity로 이동
            Log.i(TAG, "⚠️ 로그인되지 않음 → LoginActivity로 이동")
            startActivity(Intent(this, LoginActivity::class.java))
            finish()
            return
        }
        
        // 로그인 상태 확인 완료 → 정상 진행
        setContentView(R.layout.activity_test)  // 기본 레이아웃 사용
        
        // UI 참조 초기화
        statusText = findViewById(R.id.status_text)
        intentText = findViewById(R.id.intent_text)
        clarifyText = findViewById(R.id.clarify_text)
        finalAnswerText = findViewById(R.id.final_answer_text)
        logText = findViewById(R.id.log_text)
        
        // 초기 상태 표시
        updateStatus("Socket.IO 연결 대기 중...")
        addLog("🚀 MainActivitySttServer 시작")
        addLog("✅ 로그인 상태 확인 완료")
        
        // STT Repository 초기화
        sttRepository = SttRepositoryImpl(this)
        
        // Intent Repository 초기화 (더미 구현, 실제 Intent 분류는 서버에서 처리)
        intentRepository = IntentRepositoryImpl(this, null)
        
        // 세션 관리자 초기화
        sessionManager = SessionManager()
        
        // RAG Repository 초기화
        val ragRepository = RagRepositoryImpl(FASTAPI_SERVER_URL)
        llmRepository = LlmRepositoryImpl(ragRepository)
        
        // MediaPlayer Controller 초기화
        mediaPlayerController = MediaPlayerController(this)
        
        // TTS Repository 초기화
        ttsRepository = TtsRepositoryImpl(this, mediaPlayerController, FASTAPI_SERVER_URL)
        
        // Socket.IO 클라이언트 시작 (FastAPI 서버에 통합된 Socket.IO 서버에 연결)
        socketIoSttClient = SocketIoSttClient(
            serverUrl = FASTAPI_SERVER_URL,  // FastAPI 서버 URL 사용 (Socket.IO도 같은 서버)
            onSttResult = { text, type, confidence ->
                // STT 텍스트 수신 (레거시 WebSocket 대신 Socket.IO 사용)
                Log.i(TAG, "🧠 STT 텍스트 수신: type=$type, text=$text")
                addLog("🧠 STT 수신: $text")
                sttRepository.receiveFromRaspberryPi(text)
            },
            onClarifyResponse = { ragResponse ->
                // Clarify 응답 수신 처리 (레거시)
                handleClarifyResponseFromSocket(ragResponse)
            },
            onIntentResult = { intentResult ->
                // 버퍼링 STT 후 Gemini-Flash Intent 분류 결과 수신
                handleIntentResult(intentResult)
            },
            onClarifyTurn = { clarifyTurn ->
                // Clarify 질문/답변 턴 수신
                handleClarifyTurn(clarifyTurn)
            },
            onFinalAnswer = { finalAnswer ->
                // 최종 답변 수신
                handleFinalAnswerFromSocket(finalAnswer)
            },
            onStartSseConnection = { text ->
                // 버퍼링 STT 수신 시 SSE 연결 시작 요청
                handleStartSseConnection(text)
            },
            onCvDetectionFailed = { cvFailed ->
                // CV 모델 오류 탐지 실패 수신
                handleCvDetectionFailed(cvFailed)
            },
            onClarifyQaTurn = { qaTurn ->
                // Clarify 질문/답변 턴 수신 (작업자 질문 + LLM 답변)
                handleClarifyQaTurn(qaTurn)
            },
            onWakewordDetected = {
                // Wakeword 감지 이벤트 수신 (음성 파일 재생 시작)
                handleWakewordDetected()
            },
            onConnect = {
                // Socket.IO 연결 성공
                Log.i(TAG, "✅ Socket.IO 서버 연결 성공")
                updateStatus("✅ Socket.IO 연결 성공")
                addLog("✅ Socket.IO 서버 연결 성공")
            },
            onDisconnect = {
                // Socket.IO 연결 종료
                Log.i(TAG, "❌ Socket.IO 서버 연결 종료")
                updateStatus("❌ Socket.IO 연결 종료")
                addLog("❌ Socket.IO 서버 연결 종료")
            },
            onConnectError = { error ->
                // Socket.IO 연결 오류
                Log.e(TAG, "❌ Socket.IO 연결 오류: $error")
                updateStatus("❌ Socket.IO 연결 오류")
                addLog("❌ Socket.IO 연결 오류: $error")
            }
        )
        
        // 라즈베리파이 제어 API 초기화 (Socket.IO 클라이언트 사용)
        raspberryPiControlRepository = RaspberryPiControlRepository(socketIoSttClient)
        
        // 토큰 관리자 초기화 (assistant 폴더의 TokenManager는 레거시, communication의 AuthRepository 사용)
        tokenManager = TokenManager(this)
        
        // WebRTC Repository 초기화
        webRtcRepository = WebRtcRepository(SPRING_SERVER_URL)
        
        // communication 폴더의 AuthRepository를 사용하여 토큰 갱신
        // REFRESH_TOKEN으로 ACCESS_TOKEN 갱신 시도
        lifecycleScope.launch {
            val refreshToken = authRepository.getRefreshToken()
            if (refreshToken.isNotEmpty()) {
                authRepository.refreshAccessToken(refreshToken) { result ->
                    result.onSuccess {
                        Log.i(TAG, "✅ REFRESH_TOKEN으로 ACCESS_TOKEN 갱신 완료")
                        addLog("✅ 토큰 갱신 완료")
                    }.onFailure { e ->
                        Log.w(TAG, "⚠️ REFRESH_TOKEN으로 ACCESS_TOKEN 갱신 실패: ${e.message}")
                        addLog("⚠️ 토큰 갱신 실패: ${e.message}")
                        // 토큰 갱신 실패 시 로그인 화면으로 이동
                        startActivity(Intent(this@MainActivitySttServer, LoginActivity::class.java))
                        finish()
                    }
                }
            } else {
                Log.w(TAG, "⚠️ REFRESH_TOKEN이 없음 → 로그인 화면으로 이동")
                startActivity(Intent(this@MainActivitySttServer, LoginActivity::class.java))
                finish()
            }
        }
        
        try {
            socketIoSttClient.connect()
            Log.i(TAG, "✅ Socket.IO 클라이언트 연결 시작: $FASTAPI_SERVER_URL (Socket.IO 경로: /ws)")
            updateStatus("Socket.IO 연결 시도 중...")
            addLog("🔌 Socket.IO 연결 시도: $FASTAPI_SERVER_URL")
        } catch (e: Exception) {
            Log.e(TAG, "❌ Socket.IO 클라이언트 연결 실패: ${e.message}")
            e.printStackTrace()
            updateStatus("❌ Socket.IO 연결 실패")
            addLog("❌ 연결 실패: ${e.message}")
        }
    }
    
    
    /**
     * Socket.IO로부터 SSE 연결 시작 요청 수신 처리
     * 버퍼링 STT 수신 시점에 FastAPI 서버로부터 받는 이벤트
     */
    private fun handleStartSseConnection(text: String?) {
        Log.i(TAG, "📡 SSE 연결 시작 요청 수신: text=${text?.take(50)}...")
        
        lifecycleScope.launch {
            try {
                // 라즈베리파이 제어: 마이크와 buffered STT 끄기
                // 버퍼링 STT가 완료되었으므로 마이크를 끄고 대기
                // 주의: 라즈베리파이에서 버퍼링 STT 후 자동으로 마이크를 끄지만,
                // 명시적으로 제어하기 위해 notifyIntentDone을 호출하지 않음
                Log.i(TAG, "🔇 라즈베리파이 마이크 및 buffered STT 중지 (Intent 분류 대기 중)")
                
                // SSE 연결 시작
                connectSseTaskStream()
            } catch (e: Exception) {
                Log.e(TAG, "❌ SSE 연결 시작 요청 처리 실패: ${e.message}")
                e.printStackTrace()
            }
        }
    }
    
    /**
     * Socket.IO로부터 Intent 결과 수신 처리 (버퍼링 STT 후 Gemini-Flash 분류 결과)
     * Gemini-Flash가 이미 분류한 결과를 받아서 분기 처리
     */
    private fun handleIntentResult(intentResult: IntentResultDto) {
        Log.i(TAG, "📩 Intent 결과 수신: text=${intentResult.text}, intent=${intentResult.intent}, confidence=${intentResult.confidence}")
        
        lifecycleScope.launch {
            try {
                // Intent 문자열을 IntentType enum으로 변환
                val intentType = when (intentResult.intent.uppercase()) {
                    "OPERATOR" -> IntentType.OPERATOR
                    "AI_SUPPORTER" -> IntentType.AI_SUPPORTER
                    else -> {
                        Log.w(TAG, "⚠️ 알 수 없는 Intent: ${intentResult.intent}, 기본값 AI_SUPPORTER로 처리")
                        IntentType.AI_SUPPORTER
                    }
                }
                
                when (intentType) {
                    IntentType.AI_SUPPORTER -> {
                        Log.i(TAG, "✅ AI_SUPPORTER 분기 처리 시작")
                        addLog("✅ AI_SUPPORTER 분기 처리 시작")
                        
                        // 모바일 UI 업데이트: Socket.IO로 받은 intent_result 이벤트를 통해 처리
                        // 1. 음성 파일 재생 시작 시점에 "AI Supporter on" 화면 표시 (1초간)
                        runOnUiThread {
                            updateIntentUI(IntentType.AI_SUPPORTER, "AI Supporter on")
                        }
                        Log.i(TAG, "📱 UI 업데이트: AI Supporter on (1초간 표시)")
                        addLog("📱 UI: AI Supporter on")
                        
                        // 2. 1초 후 "오류 탐지 중..." 화면 표시 (CV 결과를 받을 때까지 유지)
                        lifecycleScope.launch {
                            kotlinx.coroutines.delay(1000) // 1초 대기
                            runOnUiThread {
                                updateIntentUI(IntentType.AI_SUPPORTER, "오류 탐지 중...")
                            }
                            Log.i(TAG, "📱 UI 업데이트: 오류 탐지 중... (CV 결과 대기 중)")
                            addLog("📱 UI: 오류 탐지 중...")
                        }
                        
                        // 3. 로컬 음성 파일 재생: "AI_Supporter 기능을 시작합니다. 오류 탐지."
                        Log.i(TAG, "🔊 AI_SUPPORTER 음성 파일 재생 시작: $AI_SUPPORTER_AUDIO_FILE")
                        addLog("🔊 AI_SUPPORTER 음성 파일 재생: $AI_SUPPORTER_AUDIO_FILE")
                        
                        mediaPlayerController.playLocalAudio(AI_SUPPORTER_AUDIO_FILE) {
                            // 재생 완료 콜백
                            Log.i(TAG, "✅ AI_SUPPORTER 음성 파일 재생 완료")
                            addLog("✅ AI_SUPPORTER 음성 파일 재생 완료")
                            // 음성 파일 재생 완료 후에도 "오류 탐지 중..." 화면은 CV 결과를 받을 때까지 유지됨
                        }
                        
                        // CV 모델은 FastAPI 서버에서 실행됨
                        // 오류 탐지 실패 시 cv_detection_failed 이벤트를 통해 알림 받음
                        // cv_detection_failed 이벤트 수신 시 "오류 탐지 중..." 화면이 업데이트됨
                        // 라즈베리파이 제어는 FastAPI 서버에서 cv_detection_failed 이벤트와 함께 처리됨
                        // TODO: CV 연결 구현 예정 (현재는 비워둠)
                    }
                    
                    IntentType.OPERATOR -> {
                        Log.i(TAG, "✅ OPERATOR 분기 처리 시작")
                        
                        // 1. 오디오 재생: "통신이 시작됩니다."
                        ttsRepository.speakText("통신이 시작됩니다.")
                        
                        // 2. UI 업데이트: "통신 중..." 화면 표시
                        updateIntentUI(IntentType.OPERATOR, "통신 중...")
                        
                        // 3. Spring 서버 WebRTC API 연결 요청
                        // ACCESS_TOKEN이 만료되었을 수 있으므로 갱신 시도
                        lifecycleScope.launch {
                            val accessToken = authRepository.getAccessToken()
                            if (accessToken.isNotEmpty()) {
                                // TODO: receiverAccountId를 실제 값으로 설정 (현재는 임시로 0)
                                val receiverAccountId = 0L  // 실제 수신자 계정 ID로 변경 필요
                                val success = webRtcRepository.requestConnection(accessToken, receiverAccountId)
                                if (success) {
                                    Log.i(TAG, "✅ WebRTC 연결 요청 완료")
                                } else {
                                    Log.e(TAG, "❌ WebRTC 연결 요청 실패")
                                }
                            } else {
                                Log.e(TAG, "❌ 액세스 토큰이 없어 WebRTC 연결 요청을 할 수 없습니다")
                            }
                        }
                        
                        // 라즈베리파이 제어: 마이크 resume + 모드 buffered 유지
                        raspberryPiControlRepository.notifyIntentDone("OPERATOR")
                    }
                    
                    else -> {
                        Log.w(TAG, "⚠️ 알 수 없는 Intent 타입: $intentType")
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "❌ Intent 결과 처리 실패: ${e.message}")
                e.printStackTrace()
            }
        }
    }
    
    /**
     * Intent 분기에 따른 UI 업데이트
     * 
     * @param intentType Intent 타입
     * @param message 화면에 표시할 메시지
     */
    private fun updateIntentUI(intentType: IntentType, message: String) {
        runOnUiThread {
            Log.i(TAG, "🖥️ UI 업데이트: intent=$intentType, message=$message")
            intentText.text = "Intent: $intentType - $message"
            updateStatus(message)
            addLog("📩 Intent 결과: $intentType - $message")
        }
    }
    
    /**
     * 상태 텍스트 업데이트
     */
    private fun updateStatus(message: String) {
        runOnUiThread {
            statusText.text = message
        }
    }
    
    /**
     * 로그 추가
     */
    private fun addLog(message: String) {
        runOnUiThread {
            val timestamp = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault()).format(java.util.Date())
            val logMessage = "[$timestamp] $message\n"
            logText.append(logMessage)
            // 스크롤을 맨 아래로
            val scrollView = logText.parent as? android.widget.ScrollView
            scrollView?.post {
                scrollView.fullScroll(android.view.View.FOCUS_DOWN)
            }
        }
    }
    
    /**
     * SSE 작업 스트림 연결 시작
     */
    private fun connectSseTaskStream() {
        // 액세스 토큰 확인 및 갱신
        lifecycleScope.launch {
            val accessToken = authRepository.getAccessToken()
            if (accessToken.isEmpty()) {
                Log.e(TAG, "❌ 액세스 토큰이 없습니다. 로그인이 필요합니다.")
                // 로그인 화면으로 이동
                startActivity(Intent(this@MainActivitySttServer, LoginActivity::class.java))
                finish()
                return@launch
            }
            
            // 기존 연결이 있으면 종료
            sseTaskClient?.disconnect()
            
            sseTaskClient = SseTaskClient(
                baseUrl = SPRING_SERVER_URL,
                accessToken = accessToken,
                onConnect = {
                    Log.i(TAG, "✅ SSE 작업 스트림 연결 성공")
                },
                onTaskAssign = { event ->
                    Log.i(TAG, "📋 작업 할당 수신: taskId=${event.assignedTaskId}, userName=${event.assignedUserName}")
                    // TODO: 작업 할당 UI 업데이트
                },
                onTaskCancel = { event ->
                    Log.i(TAG, "❌ 작업 취소 수신: taskId=${event.TaskId}")
                    // TODO: 작업 취소 UI 업데이트
                },
                onTaskEnd = { event ->
                    Log.i(TAG, "✅ 작업 완료 수신: taskId=${event.TaskId}")
                    // TODO: 작업 완료 UI 업데이트
                },
                onError = { error ->
                    Log.e(TAG, "❌ SSE 연결 오류: ${error.message}")
                    error.printStackTrace()
                }
            )
            
            sseTaskClient?.connect()
        }
    }
    
    /**
     * Socket.IO로부터 CV 탐지 실패 수신 처리
     * FastAPI 서버에서 CV 모델이 오류를 탐지하지 못했을 때 전송
     * "오류 탐지 중..." 화면을 업데이트함
     */
    private fun handleCvDetectionFailed(cvFailed: CvDetectionFailedDto) {
        Log.i(TAG, "📩 CV 탐지 실패 수신: ${cvFailed.message}")
        addLog("📩 CV 탐지 실패: ${cvFailed.message}")
        
        lifecycleScope.launch {
            try {
                // UI 업데이트: "오류 탐지 중..." 화면을 CV 결과 메시지로 업데이트
                val message = "오류를 탐지하지 못했습니다. AI_SUPPORTER와의 대화를 통해 문제를 해결하겠습니다. 문제 상황을 구체적으로 말씀해주세요."
                runOnUiThread {
                    updateIntentUI(IntentType.AI_SUPPORTER, message)
                }
                Log.i(TAG, "📱 UI 업데이트: CV 탐지 실패 메시지 표시")
                addLog("📱 UI: CV 탐지 실패 메시지")
                
                // 라즈베리파이 제어는 FastAPI 서버에서 cv_detection_failed 이벤트와 함께 처리됨
                // (라즈베리파이에 마이크 켜고 Streaming STT 세션 시작)
            } catch (e: Exception) {
                Log.e(TAG, "❌ CV 탐지 실패 처리 실패: ${e.message}")
                e.printStackTrace()
            }
        }
    }
    
    /**
     * Socket.IO로부터 Clarify 질문/답변 턴 수신 처리
     * Streaming STT 세션 중 Clarify 루프에서 작업자 질문 + LLM 답변 세트
     */
    private fun handleClarifyQaTurn(qaTurn: ClarifyQaTurnDto) {
        Log.i(TAG, "📩 Clarify 질문/답변 턴 수신: session_id=${qaTurn.session_id}, turn_id=${qaTurn.turn_id}, need_clarify=${qaTurn.need_clarify}")
        addLog("📩 Clarify Q&A 턴 수신: turn_id=${qaTurn.turn_id}, need_clarify=${qaTurn.need_clarify}")
        
        lifecycleScope.launch {
            try {
                if (qaTurn.status == "error") {
                    Log.e(TAG, "❌ Clarify 질문/답변 턴 오류: ${qaTurn.user_question}")
                    addLog("❌ Clarify 오류: ${qaTurn.user_question}")
                    updateStatus("Clarify 오류 발생")
                    return@launch
                }
                
                // 모바일 화면에 작업자 질문 + LLM 답변 표시
                runOnUiThread {
                    clarifyText.text = "Clarify: Q) ${qaTurn.user_question}\nA) ${qaTurn.llm_answer.take(100)}..."
                    updateStatus("Clarify 진행 중...")
                }
                
                Log.i(TAG, "💬 작업자 질문: ${qaTurn.user_question}")
                Log.i(TAG, "🤖 LLM 답변: ${qaTurn.llm_answer}")
                addLog("💬 질문: ${qaTurn.user_question}")
                addLog("🤖 답변: ${qaTurn.llm_answer.take(50)}...")
                
                // TTS 음성 파일 재생
                if (qaTurn.audio_content != null && qaTurn.audio_content.isNotBlank()) {
                    addLog("🔊 TTS 재생 시작")
                    ttsRepository.playAudio(qaTurn.audio_content, qaTurn.audio_encoding)
                }
                
                // need_clarify가 false면 최종 답변 대기 (final_answer 이벤트 수신 대기)
                if (!qaTurn.need_clarify) {
                    Log.i(TAG, "✅ 충분히 구체화됨 - 최종 답변 대기 중")
                    addLog("✅ 충분히 구체화됨 - 최종 답변 대기 중")
                    updateStatus("최종 답변 생성 중...")
                    // final_answer 이벤트를 기다림
                }
            } catch (e: Exception) {
                Log.e(TAG, "❌ Clarify 질문/답변 턴 처리 실패: ${e.message}")
                e.printStackTrace()
                addLog("❌ Clarify 처리 실패: ${e.message}")
            }
        }
    }
    
    /**
     * Socket.IO로부터 Clarify 턴 수신 처리
     */
    private fun handleClarifyTurn(clarifyTurn: ClarifyTurnDto) {
        Log.i(TAG, "💬 Clarify 턴 수신: session_id=${clarifyTurn.session_id}, turn_id=${clarifyTurn.turn_id}, status=${clarifyTurn.status}")
        
        if (clarifyTurn.status == "error") {
            Log.e(TAG, "❌ Clarify 턴 오류: ${clarifyTurn.message}")
            // TODO: 에러 처리 UI 업데이트
            return
        }
        
        if (clarifyTurn.gate_decision == "GREEN") {
            // GREEN이면 최종 답변으로 처리 (하지만 final_answer 이벤트가 별도로 올 수 있음)
            Log.d(TAG, "✅ Clarify 턴 GREEN - 최종 답변 대기 중")
            // final_answer 이벤트를 기다림
        } else {
            // RED/YELLOW: Clarify 질문 표시
            val question = clarifyTurn.question ?: ""
            val examples = clarifyTurn.examples ?: emptyList()
            
            handleClarifyResponse(question, examples)
            isWaitingForClarification = true
            currentSessionId = clarifyTurn.session_id
            currentTurnId = clarifyTurn.turn_id  // turn_id 추적
        }
    }
    
    /**
     * Socket.IO로부터 최종 답변 수신 처리
     */
    private fun handleFinalAnswerFromSocket(finalAnswer: FinalAnswerDto) {
        Log.i(TAG, "✅ 최종 답변 수신: session_id=${finalAnswer.session_id}, answer=${finalAnswer.answer.take(50)}...")
        addLog("✅ 최종 답변 수신: ${finalAnswer.answer.take(100)}...")
        
        // UI 업데이트
        runOnUiThread {
            finalAnswerText.text = "최종 답변: ${finalAnswer.answer.take(200)}..."
            updateStatus("최종 답변 수신 완료")
        }
        
        handleFinalAnswer(
            answer = finalAnswer.answer,
            audioContent = finalAnswer.audio_content,
            mimeType = finalAnswer.audio_encoding
        )
        
        // TTS 재생 로그
        if (finalAnswer.audio_content != null && finalAnswer.audio_content.isNotBlank()) {
            addLog("🔊 최종 답변 TTS 재생 시작")
        }
        
        isWaitingForClarification = false
        sessionManager.resetSession()
        currentSessionId = null
        currentTurnId = 1  // 초기화
    }
    
    /**
     * Clarify 텍스트 입력 전송
     * 
     * 사용자가 텍스트로 Clarify 응답을 입력할 때 호출합니다.
     * Socket.IO를 통해 FastAPI로 전송됩니다.
     * 
     * @param text 사용자 입력 텍스트
     * @param action "continue" | "skip" | "cancel"
     */
    fun sendClarifyTextInput(text: String, action: String = "continue") {
        val sessionId = currentSessionId
        if (sessionId == null) {
            Log.w(TAG, "⚠️ 세션 ID가 없습니다. Clarify 응답을 전송할 수 없습니다.")
            return
        }
        
        val success = socketIoSttClient.sendClarifyTextResponse(
            text = text,
            sessionId = sessionId,
            turnId = currentTurnId,
            action = action
        )
        
        if (success) {
            Log.i(TAG, "✅ Clarify 텍스트 응답 전송 완료: $text (turn_id=$currentTurnId)")
        } else {
            Log.e(TAG, "❌ Clarify 텍스트 응답 전송 실패")
        }
    }
    
    /**
     * Socket.IO로부터 Clarify 응답 수신 처리 (레거시)
     */
    private fun handleClarifyResponseFromSocket(ragResponse: com.onair.mobile.assistant.core.model.dto.RagResponse) {
        if (ragResponse.need_clarify == true) {
            // 아직 Clarify 필요
            val clarifyGuidance = ragResponse.clarify_guidance ?: ragResponse.ask ?: ""
            handleClarifyResponse(clarifyGuidance, ragResponse.options)
            // isWaitingForClarification은 이미 true 상태 유지
        } else {
            // 최종 답변 도착
            lifecycleScope.launch {
                handleFinalAnswer(ragResponse)
                isWaitingForClarification = false
                sessionManager.resetSession()
                currentSessionId = null
            }
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
        
        // UI에 Clarify 질문 표시
        runOnUiThread {
            val clarifyMessage = if (options != null && options.isNotEmpty()) {
                "$guidance\n옵션: ${options.joinToString(", ")}"
            } else {
                guidance
            }
            clarifyText.text = "Clarify: $clarifyMessage"
            updateStatus("Clarify 질문 수신")
            addLog("💬 Clarify 질문: $guidance")
        }
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
    
    /**
     * Wakeword 감지 이벤트 처리
     * 모바일에서 음성 파일 재생 후 재생 완료 신호 전송
     */
    private fun handleWakewordDetected() {
        Log.i(TAG, "📩 Wakeword 감지 이벤트 수신: 음성 파일 재생 시작")
        addLog("📩 Wakeword 감지: 음성 파일 재생 시작")
        
        lifecycleScope.launch {
            try {
                // 로컬 음성 파일 재생 (assets 폴더에 있는 파일)
                Log.i(TAG, "🔊 로컬 음성 파일 재생 시작: $WAKEWORD_AUDIO_FILE")
                addLog("🔊 음성 파일 재생: $WAKEWORD_AUDIO_FILE")
                
                // MediaPlayerController를 사용하여 로컬 파일 재생
                mediaPlayerController.playLocalAudio(WAKEWORD_AUDIO_FILE) {
                    // 재생 완료 콜백
                    Log.i(TAG, "✅ 로컬 음성 파일 재생 완료")
                    addLog("✅ 음성 파일 재생 완료")
                    
                    // FastAPI 서버로 재생 완료 이벤트 전송
                    val success = socketIoSttClient.sendWakewordAudioCompleted()
                    if (success) {
                        Log.i(TAG, "📤 모바일 음성 파일 재생 완료 이벤트 전송 완료")
                        addLog("📤 재생 완료 이벤트 전송 완료")
                    } else {
                        Log.e(TAG, "❌ 모바일 음성 파일 재생 완료 이벤트 전송 실패")
                        addLog("❌ 재생 완료 이벤트 전송 실패")
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "❌ Wakeword 감지 이벤트 처리 오류: ${e.message}")
                e.printStackTrace()
                addLog("❌ 음성 파일 재생 실패: ${e.message}")
                
                // 오류 발생 시에도 재생 완료 이벤트 전송 (타임아웃 방지)
                socketIoSttClient.sendWakewordAudioCompleted()
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        // SSE 연결 종료
        sseTaskClient?.disconnect()
        // 기타 리소스 정리
        socketIoSttClient.disconnect()
        sttRepository.cleanup()
        // intentRepository.cleanup()  // IntentRepository에는 cleanup 메서드가 없음
        ttsRepository.cleanup()
        Log.i(TAG, "🛑 리소스 정리 완료")
    }
}

