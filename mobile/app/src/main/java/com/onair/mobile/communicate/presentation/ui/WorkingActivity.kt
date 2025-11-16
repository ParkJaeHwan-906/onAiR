package com.onair.mobile.communicate.presentation.ui

import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.view.View
import android.view.animation.AnimationUtils
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.lifecycle.lifecycleScope
import com.onair.mobile.OnairApp
import com.onair.mobile.R
import com.onair.mobile.communicate.data.SseEvent
import com.onair.mobile.communicate.data.TaskRepository
import com.onair.mobile.communicate.data.WorkingRepository
import com.onair.mobile.communicate.data.api.ApiClient
import com.onair.mobile.communicate.data.api.ApiService
import com.onair.mobile.communicate.utils.viewModelByFactory
import com.onair.mobile.databinding.ActivityWorkingBinding
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import org.json.JSONObject
import com.onair.mobile.communicate.PreferenceUtil
import com.onair.mobile.communicate.data.AuthRepository
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
import com.onair.mobile.assistant.core.model.dto.CvDetectionNormalDto
import com.onair.mobile.assistant.core.model.dto.ClarifyQaTurnDto
import com.onair.mobile.assistant.data.auth.TokenManager
import com.onair.mobile.assistant.data.webrtc.WebRtcRepository

class WorkingActivity : AppCompatActivity() {
    private lateinit var binding: ActivityWorkingBinding
    private val workingViewModel: WorkingViewModel by viewModelByFactory {
        val apiService = ApiClient(this).getRetrofit().create(ApiService::class.java)
        val taskRepository = TaskRepository(apiService)
        val workingRepository = WorkingRepository(apiService)
        WorkingViewModel(taskRepository, workingRepository)
    }
    private val sseViewModel: CommunicationViewModel by lazy {
        (application as OnairApp).sseViewModel
    }


    // MainActivitySttServer 로직 통합
    private lateinit var socketIoSttClient: SocketIoSttClient
    private lateinit var sttRepository: SttRepositoryImpl
    private lateinit var intentRepository: IntentRepositoryImpl
    private lateinit var sessionManager: SessionManager
    private lateinit var llmRepository: LlmRepositoryImpl
    private lateinit var ttsRepository: TtsRepositoryImpl
    private lateinit var mediaPlayerController: MediaPlayerController
    private lateinit var raspberryPiControlRepository: RaspberryPiControlRepository
    private lateinit var tokenManager: TokenManager
    private lateinit var webRtcRepository: WebRtcRepository
    private lateinit var authRepository: AuthRepository
    private lateinit var preferenceUtil: PreferenceUtil

    private var isWaitingForClarification = false
    private var currentSessionId: String? = null
    private var currentTurnId: Int = 1
    private var aiOnDialog: AiOnDialog? = null

    private val TAG = "WorkingActivity"

    companion object {
        private const val WAKEWORD_AUDIO_FILE = "001_onAir_서비스를_시작합니다_어떤_것을_도와드릴까요.mp3"
        private const val AI_SUPPORTER_AUDIO_FILE = "001_AI_Supporter_기능을_시작합니다_오류_탐지.mp3"
        private const val OPERATOR_AUDIO_FILE = "001_통신_연결을_시작합니다.mp3"
        private const val CV_DETECTION_FAILED_AUDIO_FILE = "001_오류를_탐지하지_못했습니다_AI_Supporter와의.mp3"
        private const val CV_DETECTION_NORMAL_AUDIO_FILE = "001_탐지_결과_정상입니다_오퍼레이터와의_통신을_통해_문제.mp3"
    }

    private val FASTAPI_SERVER_URL = "https://onair.ai.kr"
    private val SPRING_SERVER_URL = "https://onair.ai.kr/api"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityWorkingBinding.inflate(layoutInflater)
        enableEdgeToEdge()
        setContentView(binding.root)

        // 로그인 상태 확인
        preferenceUtil = PreferenceUtil(applicationContext)
        val apiService = ApiClient(this).getRetrofit().create(ApiService::class.java)
        authRepository = AuthRepository(apiService, preferenceUtil)

        val refreshToken = authRepository.getRefreshToken()
        if (refreshToken.isEmpty()) {
            Log.i(TAG, "⚠️ 로그인되지 않음 → LoginActivity로 이동")
            startActivity(Intent(this, LoginActivity::class.java))
            finish()
            return
        }

        initView()
        observeViewModel()
        goCall()
        // MainActivitySttServer 로직 초기화 (연결은 onResume에서)
        initAssistantLogic()
    }


    override fun onResume() {
        super.onResume()
        // WorkingActivity가 foreground에 있을 때만 Socket.IO 연결 시작
        Log.i(TAG, "🟢 WorkingActivity onResume: Socket.IO 연결 시작")
        try {
            if (::socketIoSttClient.isInitialized) {
                socketIoSttClient.connect()
                Log.i(TAG, "✅ Socket.IO 클라이언트 연결 시작: $FASTAPI_SERVER_URL")
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ Socket.IO 클라이언트 연결 실패: ${e.message}")
            e.printStackTrace()
        }
    }

    override fun onPause() {
        super.onPause()
        // WorkingActivity가 background로 가면 Socket.IO 연결 종료
        Log.i(TAG, "🟡 WorkingActivity onPause: Socket.IO 연결 종료")
        if (::socketIoSttClient.isInitialized) {
            socketIoSttClient.disconnect()
            Log.i(TAG, "🔌 Socket.IO 연결 종료")
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        // 리소스 정리
        Log.i(TAG, "🛑 WorkingActivity onDestroy: 리소스 정리")
        if (::socketIoSttClient.isInitialized) {
            socketIoSttClient.disconnect()
        }
        if (::sttRepository.isInitialized) {
            sttRepository.cleanup()
        }
        if (::ttsRepository.isInitialized) {
            ttsRepository.cleanup()
        }
    }

    private fun initView() {
        val windowInsetsController =
            WindowCompat.getInsetsController(window, window.decorView)
        windowInsetsController.systemBarsBehavior =
            WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        windowInsetsController.hide(WindowInsetsCompat.Type.systemBars())

        val taskId = intent.getLongExtra("taskId", 0)
        val taskName = intent.getStringExtra("taskName")
        binding.taskName.text = taskName
        binding.endButton.setOnClickListener {
            workingViewModel.endTask(taskId, "")
        }
    }

    private fun observeViewModel() {
        lifecycleScope.launch {
//            repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    sseViewModel.eventFlow.collectLatest { event ->
                        Log.d("SSE_working", event.toString())
                        when (event) {
                            is SseEvent.CallRequest -> showCallRequestCard(event.data)
                            is SseEvent.CallResponse -> workingViewModel.getLiveKitToken(event.data)
                            else -> Unit
                        }
                    }
                }
                launch {
                    workingViewModel.endStatus.collect { success ->
                        if (success) {
                            setResult(RESULT_OK)
                            finish()
                        } else {
                            Toast.makeText(
                                this@WorkingActivity,
                                "작업 완료 처리 실패",
                                Toast.LENGTH_SHORT).show()
                        }
                    }
                }


        }
    }
    private fun showCallRequestCard(data: JSONObject) {
        println(data)
        println(data.getString("name"))
        Log.d("SSE_show card", data.toString())
        binding.senderInfo.text = data.getString("name")
        binding.description.text = "통신을 요청합니다: ${data.getString("description")}"

        binding.callRequestCard.visibility = View.VISIBLE
        val anim = AnimationUtils.loadAnimation(this, R.anim.cardview_slide)
        binding.callRequestCard.startAnimation(anim)

        binding.acceptCall.setOnClickListener {
            workingViewModel.responseCall(
                data.getLong("senderAccountId"), data.getString("name"), true)
        }
        binding.denyCall.setOnClickListener {
            workingViewModel.responseCall(
                data.getLong("senderAccountId"), data.getString("name"), false)
        }
    }
    private fun goCall() {
        lifecycleScope.launch {
            workingViewModel.liveKitToken.collect { token ->
                Log.d("RTC", token)
                if (!token.isNullOrBlank()) {
                    val intent = Intent(this@WorkingActivity, CallActivity::class.java).apply {
                        putExtra("server_url", "wss://onair-tbfd0pr1.livekit.cloud")
                        putExtra("token", token)
                    }
                    startActivity(intent)
                }


            }
        }
    }

    /**
     * MainActivitySttServer의 로직 초기화
     * WorkingActivity가 활성화된 상태에서만 동작하도록 설정
     */
    private fun initAssistantLogic() {
        Log.i(TAG, "🚀 Assistant 로직 초기화 시작")

        // STT Repository 초기화
        sttRepository = SttRepositoryImpl(this)

        // Intent Repository 초기화
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

        // Socket.IO 클라이언트 초기화 (연결은 onResume에서)
        socketIoSttClient = SocketIoSttClient(
            serverUrl = FASTAPI_SERVER_URL,
            onSttResult = { text, type, confidence ->
                Log.i(TAG, "🧠 STT 텍스트 수신: type=$type, text=$text")
                sttRepository.receiveFromRaspberryPi(text)
            },
            onClarifyResponse = { ragResponse ->
                handleClarifyResponseFromSocket(ragResponse)
            },
            onIntentResult = { intentResult ->
                handleIntentResult(intentResult)
            },
            onClarifyTurn = { clarifyTurn ->
                handleClarifyTurn(clarifyTurn)
            },
            onFinalAnswer = { finalAnswer ->
                handleFinalAnswerFromSocket(finalAnswer)
            },
            onStartSseConnection = null,  // 로그인 시 이미 /api/sse/stream에 연결되어 있으므로 무시
            onCvDetectionFailed = { cvFailed ->
                handleCvDetectionFailed(cvFailed)
            },
            onCvDetectionNormal = { cvNormal ->
                handleCvDetectionNormal(cvNormal)
            },
            onClarifyQaTurn = { qaTurn ->
                handleClarifyQaTurn(qaTurn)
            },
            onWakewordDetected = {
                handleWakewordDetected()
            },
            onConnect = {
                Log.i(TAG, "✅ Socket.IO 서버 연결 성공")
            },
            onDisconnect = {
                Log.i(TAG, "❌ Socket.IO 서버 연결 종료")
            },
            onConnectError = { error ->
                Log.e(TAG, "❌ Socket.IO 연결 오류: $error")
            }
        )

        // 라즈베리파이 제어 API 초기화
        raspberryPiControlRepository = RaspberryPiControlRepository(socketIoSttClient)

        // 토큰 관리자 초기화
        tokenManager = TokenManager(this)

        // WebRTC Repository 초기화
        webRtcRepository = WebRtcRepository(SPRING_SERVER_URL)

        // 토큰 갱신
        lifecycleScope.launch {
            val refreshToken = authRepository.getRefreshToken()
            if (refreshToken.isNotEmpty()) {
                authRepository.refreshAccessToken(refreshToken) { result ->
                    result.onSuccess {
                        Log.i(TAG, "✅ REFRESH_TOKEN으로 ACCESS_TOKEN 갱신 완료")
                    }.onFailure { e ->
                        Log.w(TAG, "⚠️ REFRESH_TOKEN으로 ACCESS_TOKEN 갱신 실패: ${e.message}")
                        startActivity(Intent(this@WorkingActivity, LoginActivity::class.java))
                        finish()
                    }
                }
            } else {
                Log.w(TAG, "⚠️ REFRESH_TOKEN이 없음 → 로그인 화면으로 이동")
                startActivity(Intent(this@WorkingActivity, LoginActivity::class.java))
                finish()
            }
        }

        Log.i(TAG, "✅ Assistant 로직 초기화 완료")
    }

    // MainActivitySttServer의 핵심 메서드들 (간소화 버전)
    // handleStartSseConnection 제거: 로그인 시 이미 /api/sse/stream에 연결되어 있음

    private fun handleIntentResult(intentResult: IntentResultDto) {
        Log.i(TAG, "📩 Intent 결과 수신: text=${intentResult.text}, intent=${intentResult.intent}, confidence=${intentResult.confidence}")

        lifecycleScope.launch {
            try {
                val intentType = when (intentResult.intent.uppercase()) {
                    "OPERATOR" -> IntentType.OPERATOR
                    "AI_SUPPORTER" -> IntentType.AI_SUPPORTER
                    else -> IntentType.AI_SUPPORTER
                }

                when (intentType) {
                    IntentType.AI_SUPPORTER -> {
                        Log.i(TAG, "✅ AI_SUPPORTER 분기 처리 시작")

                        // UI 업데이트: "AI Supporter on" (1초간)
                        runOnUiThread {
                            binding.taskName.text = "AI Supporter on"
                        }

                        // 1초 후 "오류 탐지 중..." 표시
                        lifecycleScope.launch {
                            kotlinx.coroutines.delay(1000)
                            runOnUiThread {
                                binding.taskName.text = "오류 탐지 중..."
                            }
                        }

                        // 음성 파일 재생
                        Log.i(TAG, "🔊 AI_SUPPORTER 음성 파일 재생 시작: $AI_SUPPORTER_AUDIO_FILE")
                        // 모달 표시
                        runOnUiThread {
                            showModal("AI 서포터 on")
                        }
                        mediaPlayerController.playLocalAudio(AI_SUPPORTER_AUDIO_FILE) {
                            // 재생 완료 콜백
                            Log.i(TAG, "✅ AI_SUPPORTER 음성 파일 재생 완료")
                            // 모달 숨기기
                            runOnUiThread {
                                hideModal()
                            }
                            
                            // FastAPI 서버로 재생 완료 이벤트 전송
                            val success = socketIoSttClient.sendIntentAudioCompleted("AI_SUPPORTER")
                            if (success) {
                                Log.i(TAG, "📤 모바일 AI_SUPPORTER 음성 파일 재생 완료 이벤트 전송 완료")
                            } else {
                                Log.e(TAG, "❌ 모바일 AI_SUPPORTER 음성 파일 재생 완료 이벤트 전송 실패")
                            }
                        }
                    }

                    IntentType.OPERATOR -> {
                        Log.i(TAG, "✅ OPERATOR 분기 처리 시작")

                        // UI 업데이트: "통신 중..." 표시
                        runOnUiThread {
                            binding.taskName.text = "통신 중..."
                        }

                        // 로컬 음성 파일 재생: "통신 연결을 시작합니다."
                        Log.i(TAG, "🔊 OPERATOR 음성 파일 재생 시작: $OPERATOR_AUDIO_FILE")
                        // 모달 표시
                        runOnUiThread {
                            showModal("통신 연결 중...")
                        }
                        mediaPlayerController.playLocalAudio(OPERATOR_AUDIO_FILE) {
                            // 재생 완료 콜백
                            Log.i(TAG, "✅ OPERATOR 음성 파일 재생 완료")
                            // 모달 숨기기
                            runOnUiThread {
                                hideModal()
                            }
                            
                            // FastAPI 서버로 재생 완료 이벤트 전송
                            val success = socketIoSttClient.sendIntentAudioCompleted("OPERATOR")
                            if (success) {
                                Log.i(TAG, "📤 모바일 OPERATOR 음성 파일 재생 완료 이벤트 전송 완료")
                            } else {
                                Log.e(TAG, "❌ 모바일 OPERATOR 음성 파일 재생 완료 이벤트 전송 실패")
                            }
                            
                            // intent_audio_completed 이벤트 전송 직후 WebRTC 요청 API 호출
                            lifecycleScope.launch {
                                val accessToken = authRepository.getAccessToken()
                                Log.i(TAG, "🔑 AccessToken 확인: 길이=${accessToken.length}, 비어있음=${accessToken.isEmpty()}")
                                
                                if (accessToken.isNotEmpty()) {
                                    // 작업자가 요청할 시 receiverAccountId는 -1로 고정 (API 문서 참조)
                                    val receiverAccountId = -1L
                                    Log.i(TAG, "📤 WebRTC 연결 요청 전송 시작: receiverAccountId=$receiverAccountId")
                                    
                                    val success = webRtcRepository.requestConnection(accessToken, receiverAccountId)
                                    if (success) {
                                        Log.i(TAG, "✅ WebRTC 연결 요청 완료 (서버 응답 성공)")
                                    } else {
                                        Log.e(TAG, "❌ WebRTC 연결 요청 실패 (서버 응답 실패 또는 오류)")
                                    }
                                } else {
                                    Log.e(TAG, "❌ AccessToken이 없어 WebRTC 연결 요청을 보낼 수 없습니다.")
                                }
                            }
                        }

                        raspberryPiControlRepository.notifyIntentDone("OPERATOR")
                    }

                    else -> {
                        Log.w(TAG, "⚠️ 알 수 없는 Intent 타입: $intentType")
                        runOnUiThread {
                            binding.taskName.text = "처리할 수 없는 요청입니다."
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "❌ Intent 결과 처리 실패: ${e.message}")
                e.printStackTrace()
            }
        }
    }

    private fun handleCvDetectionFailed(cvFailed: CvDetectionFailedDto) {
        Log.i(TAG, "📩 CV 탐지 실패 수신: ${cvFailed.message}")

        lifecycleScope.launch {
            try {
                val message = "오류를 탐지하지 못했습니다. AI_SUPPORTER와의 대화를 통해 문제를 해결하겠습니다. 문제 상황을 구체적으로 말씀해주세요."
                runOnUiThread {
                    binding.taskName.text = message
                }
                Log.i(TAG, "📱 UI 업데이트: CV 탐지 실패 메시지 표시")
                
                // CV 탐지 실패 음성 파일 재생
                Log.i(TAG, "🔊 CV 탐지 실패 음성 파일 재생 시작: $CV_DETECTION_FAILED_AUDIO_FILE")
                mediaPlayerController.playLocalAudio(CV_DETECTION_FAILED_AUDIO_FILE) {
                    Log.i(TAG, "✅ CV 탐지 실패 음성 파일 재생 완료")
                    val success = socketIoSttClient.sendCvDetectionFailedAudioCompleted()
                    if (success) {
                        Log.i(TAG, "📤 모바일 CV 탐지 실패 음성 파일 재생 완료 이벤트 전송 완료")
                    } else {
                        Log.e(TAG, "❌ 모바일 CV 탐지 실패 음성 파일 재생 완료 이벤트 전송 실패")
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "❌ CV 탐지 실패 처리 실패: ${e.message}")
                e.printStackTrace()
                // 오류 발생 시에도 재생 완료 이벤트 전송 시도
                socketIoSttClient.sendCvDetectionFailedAudioCompleted()
            }
        }
    }

    private fun handleCvDetectionNormal(cvNormal: CvDetectionNormalDto) {
        Log.i(TAG, "📩 CV 탐지 정상 수신: ${cvNormal.message}")

        lifecycleScope.launch {
            try {
                // UI 업데이트: "통신 중..." 표시
                runOnUiThread {
                    binding.taskName.text = "통신 중..."
                }
                Log.i(TAG, "📱 UI 업데이트: CV 탐지 정상 메시지 표시")
                
                // CV 탐지 정상 음성 파일 재생
                Log.i(TAG, "🔊 CV 탐지 정상 음성 파일 재생 시작: $CV_DETECTION_NORMAL_AUDIO_FILE")
                // 모달 표시
                runOnUiThread {
                    showModal("관리자에게 문제 사항을 문의 부탁드립니다. 통신 연결 중...")
                }
                mediaPlayerController.playLocalAudio(CV_DETECTION_NORMAL_AUDIO_FILE) {
                    // 재생 완료 콜백
                    Log.i(TAG, "✅ CV 탐지 정상 음성 파일 재생 완료")
                    // 모달 숨기기
                    runOnUiThread {
                        hideModal()
                    }
                    
                    // FastAPI 서버로 재생 완료 이벤트 전송
                    val success = socketIoSttClient.sendCvDetectionNormalAudioCompleted()
                    if (success) {
                        Log.i(TAG, "📤 모바일 CV 탐지 정상 음성 파일 재생 완료 이벤트 전송 완료")
                    } else {
                        Log.e(TAG, "❌ 모바일 CV 탐지 정상 음성 파일 재생 완료 이벤트 전송 실패")
                    }
                    
                    // 재생 완료 직후 WebRTC 요청 API 호출 (OPERATOR와 동일한 로직)
                    lifecycleScope.launch {
                        val accessToken = authRepository.getAccessToken()
                        Log.i(TAG, "🔑 AccessToken 확인: 길이=${accessToken.length}, 비어있음=${accessToken.isEmpty()}")
                        
                        if (accessToken.isNotEmpty()) {
                            // 작업자가 요청할 시 receiverAccountId는 -1로 고정 (API 문서 참조)
                            val receiverAccountId = -1L
                            Log.i(TAG, "📤 WebRTC 연결 요청 전송 시작: receiverAccountId=$receiverAccountId")
                            
                            val success = webRtcRepository.requestConnection(accessToken, receiverAccountId)
                            if (success) {
                                Log.i(TAG, "✅ WebRTC 연결 요청 완료 (서버 응답 성공)")
                            } else {
                                Log.e(TAG, "❌ WebRTC 연결 요청 실패 (서버 응답 실패 또는 오류)")
                            }
                        } else {
                            Log.e(TAG, "❌ AccessToken이 없어 WebRTC 연결 요청을 보낼 수 없습니다.")
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "❌ CV 탐지 정상 처리 실패: ${e.message}")
                e.printStackTrace()
                // 오류 발생 시에도 재생 완료 이벤트 전송 시도
                socketIoSttClient.sendCvDetectionNormalAudioCompleted()
            }
        }
    }

    private fun handleClarifyQaTurn(qaTurn: ClarifyQaTurnDto) {
        Log.i(TAG, "============================================================")
        Log.i(TAG, "📩 [모바일] Clarify 질문/답변 턴 수신")
        Log.i(TAG, "   Session ID: ${qaTurn.session_id}, Turn ID: ${qaTurn.turn_id}")
        Log.i(TAG, "   Gate Decision: ${qaTurn.gate_decision}")
        Log.i(TAG, "   Need Clarify: ${qaTurn.need_clarify}")
        Log.i(TAG, "============================================================")

        lifecycleScope.launch {
            try {
                if (qaTurn.status == "error") {
                    Log.e(TAG, "❌ [모바일] Clarify 질문/답변 턴 오류: ${qaTurn.user_question}")
                    return@launch
                }

                runOnUiThread {
                    binding.taskName.text = "Clarify: Q) ${qaTurn.user_question}\nA) ${qaTurn.llm_answer.take(100)}..."
                }

                Log.i(TAG, "============================================================")
                Log.i(TAG, "💬 [모바일] 작업자 질문: ${qaTurn.user_question}")
                Log.i(TAG, "🤖 [모바일] LLM 답변: ${qaTurn.llm_answer}")
                Log.i(TAG, "============================================================")

                if (qaTurn.audio_content != null && qaTurn.audio_content.isNotBlank()) {
                    Log.i(TAG, "============================================================")
                    Log.i(TAG, "🔊 [모바일] TTS 재생 시작")
                    Log.i(TAG, "   Session ID: ${qaTurn.session_id}, Turn ID: ${qaTurn.turn_id}")
                    Log.i(TAG, "   오디오 인코딩: ${qaTurn.audio_encoding}")
                    Log.i(TAG, "============================================================")
                    ttsRepository.playAudio(qaTurn.audio_content, qaTurn.audio_encoding) {
                        Log.i(TAG, "============================================================")
                        Log.i(TAG, "✅ [모바일] TTS 재생 완료")
                        Log.i(TAG, "   Session ID: ${qaTurn.session_id}, Turn ID: ${qaTurn.turn_id}")
                        Log.i(TAG, "============================================================")
                        Log.i(TAG, "============================================================")
                        Log.i(TAG, "📤 [모바일] FastAPI로 audio_playback_completed 이벤트 전송 시작")
                        Log.i(TAG, "   Type: clarify_qa_turn")
                        Log.i(TAG, "   Session ID: ${qaTurn.session_id}, Turn ID: ${qaTurn.turn_id}")
                        Log.i(TAG, "============================================================")
                        val success = socketIoSttClient.sendClarifyQaTurnAudioCompleted(
                            qaTurn.session_id ?: "",
                            qaTurn.turn_id ?: 1
                        )
                        if (success) {
                            Log.i(TAG, "============================================================")
                            Log.i(TAG, "✅ [모바일] FastAPI로 audio_playback_completed 이벤트 전송 완료")
                            Log.i(TAG, "   💡 라즈베리파이 Streaming STT는 계속 실행 중 (다음 질문 대기)")
                            Log.i(TAG, "============================================================")
                        } else {
                            Log.e(TAG, "============================================================")
                            Log.e(TAG, "❌ [모바일] FastAPI로 audio_playback_completed 이벤트 전송 실패")
                            Log.e(TAG, "============================================================")
                        }
                    }
                }

                if (!qaTurn.need_clarify) {
                    Log.i(TAG, "============================================================")
                    Log.i(TAG, "✅ [모바일] 충분히 구체화됨 - 최종 답변 대기 중")
                    Log.i(TAG, "============================================================")
                }
            } catch (e: Exception) {
                Log.e(TAG, "============================================================")
                Log.e(TAG, "❌ [모바일] Clarify 질문/답변 턴 처리 실패: ${e.message}")
                Log.e(TAG, "============================================================")
                e.printStackTrace()
            }
        }
    }

    private fun handleClarifyTurn(clarifyTurn: ClarifyTurnDto) {
        Log.i(TAG, "💬 Clarify 턴 수신: session_id=${clarifyTurn.session_id}, turn_id=${clarifyTurn.turn_id}")

        if (clarifyTurn.status == "error") {
            Log.e(TAG, "❌ Clarify 턴 오류: ${clarifyTurn.message}")
            return
        }

        if (clarifyTurn.gate_decision == "GREEN") {
            Log.d(TAG, "✅ Clarify 턴 GREEN - 최종 답변 대기 중")
        } else {
            val question = clarifyTurn.question ?: ""
            val examples = clarifyTurn.examples ?: emptyList()
            handleClarifyResponse(question, examples)
            isWaitingForClarification = true
            currentSessionId = clarifyTurn.session_id
            currentTurnId = clarifyTurn.turn_id
        }
    }

    private fun handleFinalAnswerFromSocket(finalAnswer: FinalAnswerDto) {
        Log.i(TAG, "============================================================")
        Log.i(TAG, "✅ [모바일] 최종 답변 수신 (GREEN → GPT-4o 생성 완료)")
        Log.i(TAG, "   Session ID: ${finalAnswer.session_id}, Turn ID: ${finalAnswer.turn_id}")
        Log.i(TAG, "   답변: ${finalAnswer.answer.take(100)}...")
        Log.i(TAG, "============================================================")

        runOnUiThread {
            binding.taskName.text = "최종 답변: ${finalAnswer.answer.take(200)}..."
        }

        handleFinalAnswer(
            answer = finalAnswer.answer,
            audioContent = finalAnswer.audio_content,
            mimeType = finalAnswer.audio_encoding
        )

        if (finalAnswer.audio_content != null && finalAnswer.audio_content.isNotBlank()) {
            Log.i(TAG, "============================================================")
            Log.i(TAG, "🔊 [모바일] 최종 답변 TTS 재생 시작")
            Log.i(TAG, "   Session ID: ${finalAnswer.session_id}, Turn ID: ${finalAnswer.turn_id}")
            Log.i(TAG, "   오디오 인코딩: ${finalAnswer.audio_encoding}")
            Log.i(TAG, "============================================================")
        }

        isWaitingForClarification = false
        sessionManager.resetSession()
        currentSessionId = null
        currentTurnId = 1
    }

    private fun handleClarifyResponseFromSocket(ragResponse: com.onair.mobile.assistant.core.model.dto.RagResponse) {
        if (ragResponse.need_clarify == true) {
            val clarifyGuidance = ragResponse.clarify_guidance ?: ragResponse.ask ?: ""
            handleClarifyResponse(clarifyGuidance, ragResponse.options)
        } else {
            lifecycleScope.launch {
                handleFinalAnswer(ragResponse)
                isWaitingForClarification = false
                sessionManager.resetSession()
                currentSessionId = null
            }
        }
    }

    private fun handleClarifyResponse(guidance: String, options: List<String>? = null) {
        Log.i(TAG, "💬 Clarify 질문: $guidance")

        runOnUiThread {
            val clarifyMessage = if (options != null && options.isNotEmpty()) {
                "$guidance\n옵션: ${options.joinToString(", ")}"
            } else {
                guidance
            }
            binding.taskName.text = "Clarify: $clarifyMessage"
        }
    }

    private fun handleFinalAnswer(answer: String, audioContent: String? = null, mimeType: String? = null) {
        Log.i(TAG, "============================================================")
        Log.i(TAG, "✅ [모바일] 최종 답변 처리 시작")
        Log.i(TAG, "   답변: ${answer.take(100)}...")
        Log.i(TAG, "============================================================")

        if (audioContent != null && audioContent.isNotBlank()) {
            lifecycleScope.launch {
                ttsRepository.playAudio(audioContent, mimeType) {
                    // 재생 완료 콜백
                    Log.i(TAG, "============================================================")
                    Log.i(TAG, "✅ [모바일] 최종 답변 TTS 재생 완료")
                    Log.i(TAG, "============================================================")
                    Log.i(TAG, "============================================================")
                    Log.i(TAG, "📤 [모바일] FastAPI로 audio_playback_completed 이벤트 전송 시작")
                    Log.i(TAG, "   Type: final_answer")
                    Log.i(TAG, "============================================================")
                    
                    // FastAPI 서버로 재생 완료 이벤트 전송
                    val success = socketIoSttClient.sendFinalAnswerAudioCompleted()
                    if (success) {
                        Log.i(TAG, "============================================================")
                        Log.i(TAG, "✅ [모바일] FastAPI로 audio_playback_completed 이벤트 전송 완료")
                        Log.i(TAG, "   💡 서비스 로직 종료 → Wakeword 감지 대기 상태로 복귀")
                        Log.i(TAG, "============================================================")
                    } else {
                        Log.e(TAG, "============================================================")
                        Log.e(TAG, "❌ [모바일] FastAPI로 audio_playback_completed 이벤트 전송 실패")
                        Log.e(TAG, "============================================================")
                    }
                }
            }
        } else {
            // 오디오가 없어도 재생 완료 이벤트 전송 (텍스트만 있는 경우)
            Log.i(TAG, "============================================================")
            Log.i(TAG, "📤 [모바일] FastAPI로 audio_playback_completed 이벤트 전송 시작 (오디오 없음)")
            Log.i(TAG, "   Type: final_answer")
            Log.i(TAG, "============================================================")
            val success = socketIoSttClient.sendFinalAnswerAudioCompleted()
            if (success) {
                Log.i(TAG, "============================================================")
                Log.i(TAG, "✅ [모바일] FastAPI로 audio_playback_completed 이벤트 전송 완료 (오디오 없음)")
                Log.i(TAG, "   💡 서비스 로직 종료 → Wakeword 감지 대기 상태로 복귀")
                Log.i(TAG, "============================================================")
            } else {
                Log.e(TAG, "============================================================")
                Log.e(TAG, "❌ [모바일] FastAPI로 audio_playback_completed 이벤트 전송 실패 (오디오 없음)")
                Log.e(TAG, "============================================================")
            }
        }
    }

    private suspend fun handleFinalAnswer(ragResponse: com.onair.mobile.assistant.core.model.dto.RagResponse) {
        val answer = ragResponse.result?.answer ?: ""
        val audioContent = ragResponse.result?.audio_content
        val mimeType = ragResponse.result?.mime_type

        handleFinalAnswer(answer, audioContent, mimeType)
    }

    private fun handleWakewordDetected() {
        Log.i(TAG, "📩 Wakeword 감지 이벤트 수신: 음성 파일 재생 시작")

        lifecycleScope.launch {
            try {
                Log.i(TAG, "🔊 로컬 음성 파일 재생 시작: $WAKEWORD_AUDIO_FILE")

                mediaPlayerController.playLocalAudio(WAKEWORD_AUDIO_FILE) {
                    Log.i(TAG, "✅ 로컬 음성 파일 재생 완료")

                    val success = socketIoSttClient.sendWakewordAudioCompleted()
                    if (success) {
                        Log.i(TAG, "📤 모바일 음성 파일 재생 완료 이벤트 전송 완료")
                    } else {
                        Log.e(TAG, "❌ 모바일 음성 파일 재생 완료 이벤트 전송 실패")
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "❌ Wakeword 감지 이벤트 처리 오류: ${e.message}")
                e.printStackTrace()
                socketIoSttClient.sendWakewordAudioCompleted()
            }
        }
    }

    private fun showModal(statusMessage: String) {
        if (aiOnDialog?.isVisible == true) return
        aiOnDialog = AiOnDialog(statusMessage)
        aiOnDialog?.show(supportFragmentManager, "waiting call")
    }

    private fun hideModal() {
        aiOnDialog?.dismiss()
        aiOnDialog = null
    }

    // connectSseTaskStream 제거: 로그인 시 이미 /api/sse/stream에 연결되어 있음
}