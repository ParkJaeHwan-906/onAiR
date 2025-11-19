package com.onair.mobile.communicate.presentation.ui

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaPlayer
import android.os.Bundle
import android.util.Base64
import android.util.Log
import android.view.View
import android.view.animation.AnimationUtils
import android.widget.TextView
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewModelScope
import com.google.android.material.card.MaterialCardView
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
import kotlinx.coroutines.delay
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
import com.onair.mobile.assistant.core.model.dto.CvDetectionAnomalyDto
import com.onair.mobile.assistant.core.model.dto.ClarifyQaTurnDto
import com.onair.mobile.assistant.data.auth.TokenManager
import com.onair.mobile.assistant.data.webrtc.WebRtcRepository
import com.onair.mobile.communicate.data.source.remote.SocketHolder
import io.noties.markwon.Markwon
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.File

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
    // Socket.IO 클라이언트 및 Assistant 로직
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
    private var description: String = ""  // 기본값 설정 (CV 탐지 실패/정상 케이스에서도 사용)

    private var isWaitingForClarification = false
    private var currentSessionId: String? = null
    private var currentTurnId: Int = 1
    private var aiOnDialog: AiOnDialog? = null
    private var onAirOnDialog:  OnAirOnDialog? = null
    private var isActivityResumed = false  // Activity가 resume 상태인지 추적
    private var hasSentCommunicationClose = false  // communication_close 이벤트 전송 여부 추적

    private val TAG = "WorkingActivity"

    companion object {
        private const val WAKEWORD_AUDIO_FILE = "001_onAir_서비스를_시작합니다_어떤_것을_도와드릴까요.mp3"
        private const val AI_SUPPORTER_AUDIO_FILE = "001_AI_Supporter_기능을_시작합니다_오류_탐지.mp3"
        private const val OPERATOR_AUDIO_FILE = "001_통신_연결을_시작합니다.mp3"
        private const val CV_DETECTION_FAILED_AUDIO_FILE = "001_오류_탐지에_실패하였습니다_관리자와의_통신을_통해_문.mp3"
        private const val CV_DETECTION_NORMAL_AUDIO_FILE = "001_탐지_결과_정상입니다_관리자와의_통신을_통해_문제_상.mp3"
        private const val SERVICE_END_AUDIO_FILE = "001_onAir_서비스를_종료합니다_다른_문제사항이_있으면.mp3"
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
        // Assistant 로직 초기화 (연결은 onResume에서)
        initAssistantLogic()
        showAiAnswer()
        showCvAnswer()
    }

    override fun onStart() {
        super.onStart()
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


    override fun onResume() {
        super.onResume()
        if (::socketIoSttClient.isInitialized) {
            setCallBack()
            
            // 비정상 종료 후 다시 들어온 경우를 대비하여 상태 초기화 및 wakeword 대기 상태로 복귀
            // 단, 이미 resume 상태였다가 다시 resume된 경우는 제외 (중복 방지)
            if (!isActivityResumed) {
                Log.i(TAG, "🔄 WorkingActivity onResume: 상태 초기화 및 wakeword 대기 상태로 복귀")
                resetToWakewordWaitingState()
                isActivityResumed = true
            } else {
                Log.i(TAG, "ℹ️ WorkingActivity onResume: 이미 resume 상태 (상태 초기화 생략)")
            }
        }
        // WorkingActivity가 foreground에 있을 때만 Socket.IO 연결 시작
//        Log.i(TAG, "🟢 WorkingActivity onResume: Socket.IO 연결 시작")
//        try {
//            if (::socketIoSttClient.isInitialized) {
//                socketIoSttClient.connect()
//                Log.i(TAG, "✅ Socket.IO 클라이언트 연결 시작: $FASTAPI_SERVER_URL")
//            }
//        } catch (e: Exception) {
//            Log.e(TAG, "❌ Socket.IO 클라이언트 연결 실패: ${e.message}")
//            e.printStackTrace()
//        }
    }

    override fun onPause() {
        super.onPause()
        // WorkingActivity가 background로 가면 콜백 제거 및 wakeword 대기 상태로 복귀
        Log.i(TAG, "🟡 WorkingActivity onPause: 콜백 제거 및 wakeword 대기 상태로 복귀")
        isActivityResumed = false  // pause 상태로 변경
        
        if (::socketIoSttClient.isInitialized) {
            removeCallback()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        // 리소스 정리
        Log.i(TAG, "🛑 WorkingActivity onDestroy: 리소스 정리 및 wakeword 대기 상태로 복귀")
        isActivityResumed = false  // destroy 상태로 변경
        
        // 비정상 종료 시 wakeword 대기 상태로 복귀
        // 중복 전송 방지: 아직 전송하지 않은 경우에만 전송
        if (::socketIoSttClient.isInitialized) {
            if (!hasSentCommunicationClose) {
                sendCommunicationCloseForRecovery()
                hasSentCommunicationClose = true
            } else {
                Log.i(TAG, "ℹ️ communication_close 이벤트는 이미 전송됨 (중복 방지)")
            }
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
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                socketIoSttClient.videoFrames.collect { value ->
                    value.let {
                        val bitmap = it.toBitmap()
                        val cropped = bitmap?.toBottomCropped()
                        Log.d("Demonstrate Activity", bitmap.toString())
                        Log.d("CheckBitmap", "Size: ${bitmap?.width} x ${bitmap?.height}, ByteCount: ${bitmap?.byteCount}")
                        binding.videoView.setImageBitmap(cropped)
                    }
                }
            }
        }
    }

    private fun ByteArray.toBitmap(): Bitmap? {
        return BitmapFactory.decodeByteArray(this, 0, this.size)
    }
    private fun Bitmap.toBottomCropped(targetRatio: Float = 4f/3f) : Bitmap {
        val srcWidth = this.width
        val srcHeight = this.height

        val targetHeight = (srcWidth / targetRatio).toInt()

        if (targetHeight >= srcHeight) return this

        val top = (srcHeight - targetHeight) / 2
//        val top = srcHeight - targetHeight

        return Bitmap.createBitmap(
            this,
            0, top, srcWidth,
            targetHeight
        )
    }

    private fun observeViewModel() {
        lifecycleScope.launch {
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
//                        Toast.makeText(
//                            this@WorkingActivity,
//                            "작업 완료 처리 실패",
//                            Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }
    }
    private fun showCallRequestCard(data: JSONObject) {
        Log.d("SSE_show card", data.toString())
        binding.senderInfo.text = data.getString("name")
        description = data.getString("description")
        binding.description.text = "통신을 요청합니다: ${description}"

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
                Log.d("RTC", "LiveKit 토큰 수신: ${if (token.isNotBlank()) "있음 (길이: ${token.length})" else "없음"}")
                if (token.isNotBlank()) {
                    Log.i(TAG, "============================================================")
                    Log.i(TAG, "🚀 CallActivity로 이동 시작")
                    Log.i(TAG, "   토큰: ${token.take(20)}...")
                    Log.i(TAG, "   설명: $description")
                    Log.i(TAG, "============================================================")
                    
                    val intent = Intent(this@WorkingActivity, DemonstrateActivity::class.java).apply {
//                    val intent = Intent(this@WorkingActivity, CallActivity::class.java).apply {
                        putExtra("server_url", "wss://onair-tbfd0pr1.livekit.cloud")
                        putExtra("token", token)
                        putExtra("description", description)
                    }
                    
                    // FastAPI 서버로 accept_communication 이벤트 전송
                    socketIoSttClient.sendAcceptCommunication()
                    Log.i(TAG, "📤 FastAPI 서버로 accept_communication 이벤트 전송 완료")
                    
                    startActivity(intent)
                    Log.i(TAG, "✅ CallActivity로 이동 완료")

                    binding.callRequestCard.visibility = View.GONE
                }
            }
        }
    }

    /**
     * Assistant 로직 초기화
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
        socketIoSttClient = SocketHolder.socketClient

        setCallBack()
//        socketIoSttClient = SocketIoSttClient(
//            serverUrl = FASTAPI_SERVER_URL,
//            onSttResult = { text, type, confidence ->
//                Log.i(TAG, "🧠 STT 텍스트 수신: type=$type, text=$text")
//                sttRepository.receiveFromRaspberryPi(text)
//            },
//            onClarifyResponse = { ragResponse ->
//                handleClarifyResponseFromSocket(ragResponse)
//            },
//            onIntentResult = { intentResult ->
//                handleIntentResult(intentResult)
//            },
//            onClarifyTurn = { clarifyTurn ->
//                handleClarifyTurn(clarifyTurn)
//            },
//            onFinalAnswer = { finalAnswer ->
//                handleFinalAnswerFromSocket(finalAnswer)
//            },
//            onStartSseConnection = { text ->
//                handleStartSseConnection(text)
//            },
//            onCvDetectionFailed = { cvFailed ->
//                handleCvDetectionFailed(cvFailed)
//            },
//            onClarifyQaTurn = { qaTurn ->
//                handleClarifyQaTurn(qaTurn)
//            },
//            onWakewordDetected = {
//                handleWakewordDetected()
//            },
//            onConnect = {
//                Log.i(TAG, "✅ Socket.IO 서버 연결 성공")
//            },
//            onDisconnect = {
//                Log.i(TAG, "❌ Socket.IO 서버 연결 종료")
//            },
//            onConnectError = { error ->
//                Log.e(TAG, "❌ Socket.IO 연결 오류: $error")
//            }
//        )

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

    // Assistant 핵심 메서드들
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

                        // 모달 표시: "AI 서포터 on"
                        runOnUiThread {
                            showModal("AI 서포터 on")
                        }

                        // AI Supporter 시작 오디오 재생
                        Log.i(TAG, "🔊 AI_SUPPORTER 음성 파일 재생 시작: $AI_SUPPORTER_AUDIO_FILE")
                        mediaPlayerController.playLocalAudio(AI_SUPPORTER_AUDIO_FILE) {
                            // 재생 완료 콜백
                            Log.i(TAG, "✅ AI_SUPPORTER 음성 파일 재생 완료")
                            
                            // 모달 텍스트를 "AI 서포터가 오류 탐지 중..."으로 변경
                            runOnUiThread {
                                aiOnDialog?.updateMessage("AI 서포터가 오류 탐지 중...")
                            }
                            
                            // 2초 대기 후 FastAPI 서버로 재생 완료 이벤트 전송
                            lifecycleScope.launch {
                                kotlinx.coroutines.delay(2000)
                                
                                val success = socketIoSttClient.sendIntentAudioCompleted("AI_SUPPORTER")
                                if (success) {
                                    Log.i(TAG, "📤 모바일 AI_SUPPORTER 음성 파일 재생 완료 이벤트 전송 완료")
                                } else {
                                    Log.e(TAG, "❌ 모바일 AI_SUPPORTER 음성 파일 재생 완료 이벤트 전송 실패")
                                }
                                
                                // 모달은 CV 탐지 결과가 오면 자동으로 처리됨 (hideModal은 CV 탐지 결과에서 처리)
                            }
                        }
                    }

                    IntentType.OPERATOR -> {
                        Log.i(TAG, "✅ OPERATOR 분기 처리 시작")

                        // UI 업데이트: "통신 중..." 표시
                        runOnUiThread {
//                            binding.taskName.text = "통신 중..."
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
                                
                                // 라즈베리파이 제어: 마이크 resume + 모드 buffered 유지 (CV 탐지 실패/정상과 동일한 로직)
                                raspberryPiControlRepository.notifyIntentDone("OPERATOR")
                            }
                        }
                    }

                    else -> {
                        Log.w(TAG, "⚠️ 알 수 없는 Intent 타입: $intentType")
                        runOnUiThread {
//                            binding.taskName.text = "처리할 수 없는 요청입니다."
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
                // UI 업데이트: "통신 중..." 표시 (normal과 동일)
                runOnUiThread {
//                    binding.taskName.text = "통신 중..."
                }
                Log.i(TAG, "📱 UI 업데이트: CV 탐지 실패 메시지 표시")

                // 모달 텍스트를 "관리자에게 문제 사항을 문의 부탁드립니다. 통신 연결 중..."으로 변경 (오디오 재생과 동시에)
                runOnUiThread {
                    aiOnDialog?.updateMessage("관리자에게 문제 사항을 문의 부탁드립니다. 통신 연결 중...")
                }
                
                // CV 탐지 실패 음성 파일 재생
                Log.i(TAG, "🔊 CV 탐지 실패 음성 파일 재생 시작: $CV_DETECTION_FAILED_AUDIO_FILE")
                mediaPlayerController.playLocalAudio(CV_DETECTION_FAILED_AUDIO_FILE) {
                    // 재생 완료 콜백
                    Log.i(TAG, "✅ CV 탐지 실패 음성 파일 재생 완료")

                    // FastAPI 서버로 재생 완료 이벤트 전송
                    val success = socketIoSttClient.sendCvDetectionFailedAudioCompleted()
                    if (success) {
                        Log.i(TAG, "📤 모바일 CV 탐지 실패 음성 파일 재생 완료 이벤트 전송 완료")
                    } else {
                        Log.e(TAG, "❌ 모바일 CV 탐지 실패 음성 파일 재생 완료 이벤트 전송 실패")
                    }

                    // WebRTC 연결 요청 전송 (OPERATOR와 동일한 로직)
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
                        
                        // 라즈베리파이 제어: 마이크 resume + 모드 buffered 유지 (OPERATOR와 동일한 로직)
                        raspberryPiControlRepository.notifyIntentDone("OPERATOR")
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

    private fun handleCvDetectionAnomaly(cvAnomaly: CvDetectionAnomalyDto) {
        // showCvAnswer() 함수가 cvAnswer Flow를 collect하고 있어서
        // SocketIoSttClient에서 _cvAnswer.tryEmit(cvAnomaly)를 호출하면
        // 자동으로 showCvAnswer()의 collect가 트리거됩니다.
        // 따라서 이 함수에서는 추가 처리 없이 로그만 남깁니다.
        Log.i(TAG, "============================================================")
        Log.i(TAG, "✅ [모바일] CV 탐지 이상 이벤트 수신 (showCvAnswer 함수로 처리)")
        Log.i(TAG, "   메시지: ${cvAnomaly.message}")
        Log.i(TAG, "   💡 SocketIoSttClient에서 cvAnswer Flow에 emit → showCvAnswer() 자동 실행")
        Log.i(TAG, "============================================================")
    }

    private fun handleCvDetectionNormal(cvNormal: CvDetectionNormalDto) {
        Log.i(TAG, "📩 CV 탐지 정상 수신: ${cvNormal.message}")

        lifecycleScope.launch {
            try {
                // UI 업데이트: "통신 중..." 표시
                runOnUiThread {
//                    binding.taskName.text = "통신 중..."
                }
                Log.i(TAG, "📱 UI 업데이트: CV 탐지 정상 메시지 표시")

                // 모달 텍스트를 "관리자에게 문제 사항을 문의 부탁드립니다. 통신 연결 중..."으로 변경 (오디오 재생과 동시에)
                runOnUiThread {
                    aiOnDialog?.updateMessage("관리자에게 문제 사항을 문의 부탁드립니다. 통신 연결 중...")
                }
                
                // CV 탐지 정상 음성 파일 재생
                Log.i(TAG, "🔊 CV 탐지 정상 음성 파일 재생 시작: $CV_DETECTION_NORMAL_AUDIO_FILE")
                mediaPlayerController.playLocalAudio(CV_DETECTION_NORMAL_AUDIO_FILE) {
                    // 재생 완료 콜백
                    Log.i(TAG, "✅ CV 탐지 정상 음성 파일 재생 완료")

                    // FastAPI 서버로 재생 완료 이벤트 전송
                    val success = socketIoSttClient.sendCvDetectionNormalAudioCompleted()
                    if (success) {
                        Log.i(TAG, "📤 모바일 CV 탐지 정상 음성 파일 재생 완료 이벤트 전송 완료")
                    } else {
                        Log.e(TAG, "❌ 모바일 CV 탐지 정상 음성 파일 재생 완료 이벤트 전송 실패")
                    }

                    // WebRTC 연결 요청 전송 (OPERATOR와 동일한 로직)
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
                        
                        // 라즈베리파이 제어: 마이크 resume + 모드 buffered 유지 (OPERATOR와 동일한 로직)
                        raspberryPiControlRepository.notifyIntentDone("OPERATOR")
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
//                    binding.taskName.text = "Clarify: Q) ${qaTurn.user_question}\nA) ${qaTurn.llm_answer.take(100)}..."
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

        // 모달 숨기기 ("답변 생성 중..." 모달)
        runOnUiThread {
            hideModal()
        }
        
        // 간단한 알림 메시지 카드 숨기기 (확실하게)
        // final_answer 수신 시 간단한 알림 카드가 아직 표시되어 있을 수 있으므로 확실히 숨김
        runOnUiThread {
            binding.cvResultError.visibility = View.GONE
            binding.cvResultError.alpha = 0f
            binding.cvResultError.clearAnimation()  // 진행 중인 애니메이션 취소
        }
        
        // 간단한 알림 카드가 완전히 사라진 후 섹션별 카드 표시를 위해 짧은 딜레이
        lifecycleScope.launch {
            delay(100)  // 100ms 딜레이로 간단한 알림 카드가 완전히 사라지도록 보장
            
            // 각 섹션별 말풍선 표시 및 오디오 재생
            val structuredAnswer = finalAnswer.structured_answer
            if (structuredAnswer != null) {
                handleStructuredAnswerSections(structuredAnswer)
            } else {
                // Fallback: 기존 방식 (전체 오디오 재생)
                handleFinalAnswer(
                    answer = finalAnswer.answer,
                    audioContent = finalAnswer.audio_content,
                    mimeType = finalAnswer.audio_encoding
                )
            }
        }

        isWaitingForClarification = false
        sessionManager.resetSession()
        currentSessionId = null
        currentTurnId = 1
    }

    /**
     * 각 섹션별(possible_causes, recommended_actions, safety_warnings) 말풍선 표시 및 오디오 재생
     * 마지막 섹션의 오디오 재생 완료 후 서비스 종료 처리
     */
    private fun handleStructuredAnswerSections(structuredAnswer: Map<String, Any>) {
        Log.i(TAG, "============================================================")
        Log.i(TAG, "📋 [모바일] 각 섹션별 말풍선 표시 및 오디오 재생 시작")
        Log.i(TAG, "============================================================")

        lifecycleScope.launch {
            try {
                // 1. possible_causes (원인) - 마크다운 텍스트 + 오디오
                val possibleCausesMarkdown = structuredAnswer["possible_causes_markdown"] as? String
                val possibleCausesAudio = structuredAnswer["possible_causes_audio"] as? String
                val possibleCausesAudioEncoding = structuredAnswer["possible_causes_audio_encoding"] as? String

                // 2. recommended_actions (조치) - 마크다운 텍스트 + 오디오
                val recommendedActionsMarkdown = structuredAnswer["recommended_actions_markdown"] as? String
                val recommendedActionsAudio = structuredAnswer["recommended_actions_audio"] as? String
                val recommendedActionsAudioEncoding = structuredAnswer["recommended_actions_audio_encoding"] as? String

                // 3. safety_warnings (주의사항) - 마크다운 텍스트 + 오디오
                val safetyWarningsMarkdown = structuredAnswer["safety_warnings_markdown"] as? String
                val safetyWarningsAudio = structuredAnswer["safety_warnings_audio"] as? String
                val safetyWarningsAudioEncoding = structuredAnswer["safety_warnings_audio_encoding"] as? String

                // 각 섹션별 처리 (순차적으로)
                Log.i(TAG, "============================================================")
                Log.i(TAG, "📋 [모바일] 섹션별 처리 시작 (원인 → 조치 → 주의사항)")
                Log.i(TAG, "============================================================")
                
                processSection(
                    sectionName = "원인",
                    markdownText = possibleCausesMarkdown,
                    audioContent = possibleCausesAudio,
                    audioEncoding = possibleCausesAudioEncoding,
                    isLastSection = false
                ) {
                    // possible_causes 완료 후 바로 다음 섹션 진행
                    Log.i(TAG, "✅ [모바일] 원인 섹션 완료, 조치 섹션 시작")
                    processSection(
                        sectionName = "조치",
                        markdownText = recommendedActionsMarkdown,
                        audioContent = recommendedActionsAudio,
                        audioEncoding = recommendedActionsAudioEncoding,
                        isLastSection = false
                    ) {
                        // recommended_actions 완료 후 바로 다음 섹션 진행
                        Log.i(TAG, "✅ [모바일] 조치 섹션 완료, 주의사항 섹션 시작")
                        processSection(
                            sectionName = "주의사항",
                            markdownText = safetyWarningsMarkdown,
                            audioContent = safetyWarningsAudio,
                            audioEncoding = safetyWarningsAudioEncoding,
                            isLastSection = true
                        ) {
                            // 마지막 섹션 완료 → 서비스 종료 처리
                            Log.i(TAG, "============================================================")
                            Log.i(TAG, "✅ [모바일] 모든 섹션 처리 완료")
                            Log.i(TAG, "📤 [모바일] FastAPI로 audio_playback_completed 이벤트 전송 시작")
                            Log.i(TAG, "   Type: final_answer")
                            Log.i(TAG, "   💡 서비스 로직 종료 → Wakeword 감지 대기 상태로 복귀")
                            Log.i(TAG, "============================================================")

                            val success = socketIoSttClient.sendFinalAnswerAudioCompleted()
                            if (success) {
                                Log.i(TAG, "✅ [모바일] FastAPI로 audio_playback_completed 이벤트 전송 완료")
                            } else {
                                Log.e(TAG, "❌ [모바일] FastAPI로 audio_playback_completed 이벤트 전송 실패")
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "❌ 섹션별 처리 오류: ${e.message}")
                e.printStackTrace()
                // 오류 발생 시에도 서비스 종료 처리
                socketIoSttClient.sendFinalAnswerAudioCompleted()
            }
        }
    }

    /**
     * 각 섹션 처리 (마크다운 말풍선 표시 + 오디오 재생)
     */
    private suspend fun processSection(
        sectionName: String,
        markdownText: String?,
        audioContent: String?,
        audioEncoding: String?,
        isLastSection: Boolean,
        onComplete: suspend () -> Unit
    ) {
        Log.i(TAG, "============================================================")
        Log.i(TAG, "📋 [모바일] 섹션 처리 시작: $sectionName")
        Log.i(TAG, "============================================================")

        // 섹션별 CardView와 TextView 매핑
        val (cardView, textView) = when (sectionName) {
            "원인" -> Pair(binding.aiResultCause, binding.aiResultCauseText)
            "조치" -> Pair(binding.aiResultAction, binding.aiResultActionText)
            "주의사항" -> Pair(binding.aiResultWarning, binding.aiResultWarningText)
            else -> {
                Log.w(TAG, "⚠️ 알 수 없는 섹션: $sectionName")
                // 기본값으로 원인 섹션 사용
                Pair(binding.aiResultCause, binding.aiResultCauseText)
            }
        }

        // 마크다운 텍스트가 있으면 runSection() 호출하여 UI 표시 및 오디오 재생
        if (markdownText != null && markdownText.isNotBlank()) {
            Log.i(TAG, "💬 [UI] $sectionName 마크다운 말풍선 표시 시작")
            runSection(
                cardView = cardView,
                textView = textView,
                text = markdownText,
                audioBase64 = audioContent
            )
            Log.i(TAG, "✅ [UI] $sectionName 마크다운 말풍선 표시 및 오디오 재생 완료")
        } else {
            // 마크다운 텍스트가 없으면 오디오만 재생
            Log.w(TAG, "⚠️ [UI] $sectionName 마크다운 텍스트가 없습니다. 오디오만 재생합니다.")
            if (audioContent != null && audioContent.isNotBlank()) {
                playAudio(audioContent)
            }
        }

        // runSection() 완료 후 완료 콜백 호출 (다음 섹션 진행)
        Log.i(TAG, "============================================================")
        Log.i(TAG, "📋 [모바일] $sectionName 섹션 처리 완료, 다음 섹션으로 진행")
        Log.i(TAG, "============================================================")
        onComplete()
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
//            binding.taskName.text = "Clarify: $clarifyMessage"
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
        
        // Wakeword 감지 시 communication_close 플래그 리셋 (새로운 서비스 시작)
        hasSentCommunicationClose = false

        lifecycleScope.launch {
            try {
                Log.i(TAG, "🔊 로컬 음성 파일 재생 시작: $WAKEWORD_AUDIO_FILE")

                runOnUiThread {
                    showOnModal()
                }

                mediaPlayerController.playLocalAudio(WAKEWORD_AUDIO_FILE) {
                    Log.i(TAG, "✅ 로컬 음성 파일 재생 완료")

                    val success = socketIoSttClient.sendWakewordAudioCompleted()
                    if (success) {
                        Log.i(TAG, "📤 모바일 음성 파일 재생 완료 이벤트 전송 완료")
                        runOnUiThread {
                            hideOnModal()
                        }
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

    private fun handlePlayServiceEndAudio(audioFile: String) {
        Log.i(TAG, "============================================================")
        Log.i(TAG, "📩 서비스 종료 오디오 재생 요청 수신")
        Log.i(TAG, "   파일: $audioFile")
        Log.i(TAG, "============================================================")

        lifecycleScope.launch {
            try {
                // 파일명이 제공되지 않으면 기본 파일 사용
                val fileToPlay = if (audioFile.isNotBlank()) audioFile else SERVICE_END_AUDIO_FILE
                Log.i(TAG, "🔊 서비스 종료 오디오 재생 시작: $fileToPlay")

                // 서비스 종료 오디오 재생 시 OnAir 모달 표시
                runOnUiThread {
                    showOnModal()
                }

                mediaPlayerController.playLocalAudio(fileToPlay) {
                    Log.i(TAG, "============================================================")
                    Log.i(TAG, "✅ 서비스 종료 오디오 재생 완료")
                    Log.i(TAG, "📤 FastAPI로 audio_playback_completed (type: service_completed) 이벤트 전송 시작")
                    Log.i(TAG, "============================================================")

                    val success = socketIoSttClient.sendServiceCompletedAudioCompleted()
                    if (success) {
                        Log.i(TAG, "✅ [모바일] FastAPI로 service_completed 이벤트 전송 완료")
                        Log.i(TAG, "   💡 Wakeword 감지 대기 상태로 복귀")
                    } else {
                        Log.e(TAG, "❌ [모바일] FastAPI로 service_completed 이벤트 전송 실패")
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "❌ 서비스 종료 오디오 재생 오류: ${e.message}")
                e.printStackTrace()
                // 오류 발생 시에도 이벤트 전송
                socketIoSttClient.sendServiceCompletedAudioCompleted()
            }
        }
    }
 
    private fun showModal(statusMessage: String) {
        if (aiOnDialog?.isVisible == true) return
        aiOnDialog = AiOnDialog(statusMessage)
        aiOnDialog?.show(supportFragmentManager, "waiting call")
    }
    private fun showOnModal() {
        Log.d("show on modal", "모달 호출")
        if (onAirOnDialog?.isVisible == true) return
        onAirOnDialog = OnAirOnDialog()
        onAirOnDialog?.show(supportFragmentManager, "onAiR on")
    }

    private fun hideModal() {
        aiOnDialog?.dismiss()
        aiOnDialog = null
    }
    private fun hideOnModal() {
        onAirOnDialog?.dismiss()
        onAirOnDialog = null
    }
    private fun showCvAnswer() {
        lifecycleScope.launch {
            workingViewModel.cvAnswer.collect { value ->
                Log.i(TAG, "============================================================")
                Log.i(TAG, "✅ [모바일] CV 탐지 이상 수신 (showCvAnswer 함수)")
                Log.i(TAG, "   메시지: ${value.message}")
                Log.i(TAG, "============================================================")
                
                // "AI 서포터가 오류 탐지 중" 모달 숨기기
                runOnUiThread {
                    hideModal()
                }
                
                binding.cvResultError.visibility = View.VISIBLE
                withContext(Dispatchers.Main) {
                    binding.cvResultError.slideIn()
                }
                withContext(Dispatchers.Main) {
                    showTypingEffect(binding.cvResultErrorText, value.message)
                }
                
                // 오디오 재생
                if (value.audio_content != null && value.audio_content.isNotBlank()) {
                    Log.i(TAG, "🔊 CV 탐지 이상 알림 TTS 재생 시작")
                    playAudio(value.audio_content)
                    Log.i(TAG, "✅ CV 탐지 이상 알림 TTS 재생 완료")
                } else {
                    Log.w(TAG, "⚠️ CV 탐지 이상 알림 오디오가 없습니다")
                }
                
                // 오디오 재생 완료 후 바로 카드 fadeOut (완료까지 대기)
                binding.cvResultError.fadeOut()  // suspend 함수이므로 완료까지 자동으로 대기
                // fadeOut 완료 후 visibility를 GONE으로 설정하여 다음 섹션과 겹치지 않도록
                withContext(Dispatchers.Main) {
                    binding.cvResultError.visibility = View.GONE
                }
                
                // 모달 표시 ("답변 생성 중...")
                runOnUiThread {
                    showModal("답변 생성 중...")
                }
                
                // FastAPI 서버로 재생 완료 이벤트 전송
                val success = socketIoSttClient.sendCvDetectionAnomalyAudioCompleted()
                if (success) {
                    Log.i(TAG, "📤 모바일 CV 탐지 이상 음성 파일 재생 완료 이벤트 전송 완료")
                    Log.i(TAG, "   💡 모달 표시 중: '답변 생성 중...'")
                    Log.i(TAG, "   💡 final_answer 수신 시 모달 자동 숨김")
                } else {
                    Log.e(TAG, "❌ 모바일 CV 탐지 이상 음성 파일 재생 완료 이벤트 전송 실패")
                    // 전송 실패해도 모달은 유지 (final_answer 수신 시 숨김)
                }
            }
        }
    }
    private fun showAiAnswer() {
        lifecycleScope.launch {
            workingViewModel.finalAnswer.collect { answer ->
                Log.d(TAG, answer.markdown_text)
                runSection(
                    binding.aiResultCause,
                    binding.aiResultCauseText,
                    answer.possible_causes_markdown,
                    answer.possible_causes_audio
                )
                runSection(
                    binding.aiResultAction,
                    binding.aiResultActionText,
                    answer.recommended_actions_markdown,
                    answer.recommended_actions_audio
                )
                runSection(
                    binding.aiResultWarning,
                    binding.aiResultWarningText,
                    answer.safety_warnings_markdown,
                    answer.safety_warnings_audio
                )
            }
        }
    }
    suspend fun runSection(
        cardView: MaterialCardView,
        textView: TextView,
        text: String,
        audioBase64: String?
    ) {
        // 이전 섹션 카드가 완전히 사라졌는지 확인
        cardView.visibility = View.VISIBLE
        withContext(Dispatchers.Main) {
            cardView.slideIn()
        }
        withContext(Dispatchers.Main) {
            showTypingEffect(textView, text)
        }
        // 오디오 재생 완료까지 대기
        playAudio(audioBase64)
        // 오디오 재생 완료 후 바로 카드 fadeOut (완료까지 대기)
        cardView.fadeOut()  // suspend 함수이므로 완료까지 자동으로 대기
        // fadeOut 완료 후 visibility를 GONE으로 설정하여 다음 섹션과 겹치지 않도록
        withContext(Dispatchers.Main) {
            cardView.visibility = View.GONE
        }
    }
    suspend fun showTypingEffect(textView: TextView, text: String) {
        val markwon = Markwon.create(textView.context)

        for (i in 1..text.length) {
            val sub = text.substring(0, i)
            markwon.setMarkdown(textView, sub)
            delay(15)
        }
    }
    suspend fun playAudio(base64: String?) {
        Log.d(TAG, "오디오 base64: $base64")
        if (base64 == null || base64.isBlank()) {
            Log.w(TAG, "⚠️ 오디오 base64가 null이거나 비어있습니다")
            return
        }

        val audioBytes = Base64.decode(base64, Base64.DEFAULT)
        val tempFile = File.createTempFile("tts", ".mp3")

        tempFile.writeBytes(audioBytes)

        val player = MediaPlayer().apply {
            setDataSource(tempFile.path)
        }
        val completion = CompletableDeferred<Unit>()
        player.setOnCompletionListener {
            completion.complete(Unit)
            player.release()
            tempFile.delete()  // 임시 파일 삭제
        }
        player.setOnErrorListener { _, what, extra ->
            Log.e(TAG, "❌ MediaPlayer 오류: what=$what, extra=$extra")
            completion.complete(Unit)  // 오류 발생 시에도 완료 처리
            player.release()
            tempFile.delete()
            true
        }
        try {
            player.prepare()
            player.start()
            Log.d(TAG, "✅ 오디오 재생 시작")
            completion.await()  // 재생 완료까지 대기
            Log.d(TAG, "✅ 오디오 재생 완료")
        } catch (e: Exception) {
            Log.e(TAG, "❌ 오디오 재생 오류: ${e.message}")
            e.printStackTrace()
            completion.complete(Unit)
            player.release()
            tempFile.delete()
        }

        completion.await()
    }

    fun View.slideIn(duration:Long = 400) {
        this.translationX = -300f
        this.alpha = 0f
        this.animate()
            .translationX(0f)
            .alpha(1f)
            .setDuration(duration)
            .start()
    }

    suspend fun View.fadeOut(duration: Long = 400) {
        val job = CompletableDeferred<Unit>()
        this.animate()
            .alpha(0f)
            .setDuration(duration)
            .withEndAction { job.complete(Unit) }
            .start()
        job.await()
    }


    private fun setCallBack() {
        socketIoSttClient.setCallbacks(
            onSttResult = { text, type, confidence ->
                Log.i(TAG, "🧠 STT 텍스트 수신: $text")
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
            onCvDetectionNormal = { cvNormal ->
                handleCvDetectionNormal(cvNormal)
            },
            onCvDetectionFailed = { cv ->
                handleCvDetectionFailed(cv)
            },
            onCvDetectionAnomaly = { cvAnomaly ->
                handleCvDetectionAnomaly(cvAnomaly)
            },
            onClarifyQaTurn = { qa ->
                handleClarifyQaTurn(qa)
            },
            onWakewordDetected = {
                handleWakewordDetected()
            },
            onPlayServiceEndAudio = { audioFile ->
                handlePlayServiceEndAudio(audioFile)
            },
            onConnect = {
                Log.i(TAG, "✅ Socket.IO 서버 연결 성공")
            },
            onDisconnect = {
                Log.i(TAG, "❌ Socket.IO 서버 연결 종료")
            },
            onConnectError = { error ->
                Log.e(TAG, "❌ Socket 연결 오류: $error")
            }
        )
    }

    private fun removeCallback() {
        socketIoSttClient.setCallbacks(
            onSttResult = null,
            onClarifyResponse = null,
            onIntentResult = null,
            onClarifyTurn = null,
            onFinalAnswer = null,
            onStartSseConnection = null,
            onCvDetectionNormal = null,
            onCvDetectionFailed = null,
            onCvDetectionAnomaly = null,
            onClarifyQaTurn = null,
            onWakewordDetected = null,
            onPlayServiceEndAudio = null,
        )
    }
    
    /**
     * 비정상 종료 시 wakeword 대기 상태로 복귀하기 위한 통신 종료 이벤트 전송
     */
    private fun sendCommunicationCloseForRecovery() {
        try {
            if (::socketIoSttClient.isInitialized && socketIoSttClient.isConnected()) {
                val success = socketIoSttClient.sendCommunicationClose()
                if (success) {
                    Log.i(TAG, "✅ 통신 종료 이벤트 전송 완료 (wakeword 대기 상태로 복귀)")
                    hasSentCommunicationClose = true
                } else {
                    Log.w(TAG, "⚠️ 통신 종료 이벤트 전송 실패 (Socket.IO 연결 상태 확인 필요)")
                }
            } else {
                Log.w(TAG, "⚠️ Socket.IO 클라이언트가 연결되어 있지 않아 통신 종료 이벤트를 전송할 수 없습니다")
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ 통신 종료 이벤트 전송 중 오류: ${e.message}")
            e.printStackTrace()
        }
    }
    
    /**
     * 상태 초기화 및 wakeword 대기 상태로 복귀
     * (onResume에서 호출하여 비정상 종료 후 다시 들어온 경우를 처리)
     */
    private fun resetToWakewordWaitingState() {
        try {
            Log.i(TAG, "🔄 상태 초기화 시작")
            
            // 세션 상태 초기화
            isWaitingForClarification = false
            currentSessionId = null
            currentTurnId = 1
            sessionManager.resetSession()
            
            // UI 초기화
            runOnUiThread {
//                binding.taskName.text = "대기 중..."
                hideModal()
            }
            
            // 통신 종료 이벤트 전송 (wakeword 대기 상태로 복귀)
            // 중복 전송 방지: 아직 전송하지 않은 경우에만 전송
            if (::socketIoSttClient.isInitialized && socketIoSttClient.isConnected()) {
                if (!hasSentCommunicationClose) {
                    val success = socketIoSttClient.sendCommunicationClose()
                    if (success) {
                        Log.i(TAG, "✅ 상태 초기화 및 wakeword 대기 상태로 복귀 완료")
                        hasSentCommunicationClose = true
                    } else {
                        Log.w(TAG, "⚠️ 통신 종료 이벤트 전송 실패 (Socket.IO 연결 상태 확인 필요)")
                    }
                } else {
                    Log.i(TAG, "ℹ️ communication_close 이벤트는 이미 전송됨 (상태 초기화만 수행)")
                }
            } else {
                Log.w(TAG, "⚠️ Socket.IO 클라이언트가 연결되어 있지 않아 상태 복귀 이벤트를 전송할 수 없습니다")
            }
            
            // 다음 wakeword 감지를 위해 플래그 리셋
            hasSentCommunicationClose = false
        } catch (e: Exception) {
            Log.e(TAG, "❌ 상태 초기화 중 오류: ${e.message}")
            e.printStackTrace()
        }
    }
}