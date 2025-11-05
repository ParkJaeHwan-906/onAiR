package com.onair.mobile.assistant.domain.usecase

import android.util.Log
import com.onair.mobile.assistant.core.common.SessionManager
import com.onair.mobile.assistant.core.model.dto.IntentClassificationDto
import com.onair.mobile.assistant.domain.entity.IntentType
import com.onair.mobile.assistant.domain.repository.LlmRepository

/**
 * Intent 분류 결과에 따라 적절한 처리 경로로 분기하는 UseCase
 * 
 * 플로우:
 * - OPERATOR → RTC Start
 * - AI_SUPPORTER → RAG API 호출 → Clarify 또는 최종 답변
 */
class DispatchIntentUseCase(
    private val detectObjectUseCase: DetectObjectUseCase? = null,
    private val llmRepository: LlmRepository? = null,
    private val sessionManager: SessionManager
) {

    private val TAG = "DispatchIntentUseCase"

    /**
     * Intent 분류 결과를 받아서 적절한 처리 경로로 분기
     * 
     * @param intentResult Intent 분류 결과
     * @return 처리 결과
     */
    suspend operator fun invoke(intentResult: IntentClassificationDto): DispatchResult {
        Log.i(TAG, "🔄 Intent 분기 처리 시작: ${intentResult.intentType.value}")

        return when (intentResult.intentType) {
            IntentType.OPERATOR -> {
                Log.i(TAG, "👤 Operator Intent → RTC Start")
                handleOperatorIntent(intentResult)
            }
            
            IntentType.AI_SUPPORTER -> {
                Log.i(TAG, "🤖 AI Supporter Intent → Vision Analyzer")
                handleAiSupporterIntent(intentResult)
            }
            
            IntentType.UNKNOWN -> {
                Log.w(TAG, "❓ Unknown Intent: ${intentResult.rawText}")
                DispatchResult.Error("알 수 없는 Intent입니다.")
            }
        }
    }

    /**
     * Operator Intent 처리
     * RTC(Real-Time Communication) 연결 시작
     */
    private suspend fun handleOperatorIntent(intentResult: IntentClassificationDto): DispatchResult {
        try {
            // TODO: RTC Start 로직 구현
            Log.i(TAG, "📞 RTC Start 호출 준비: ${intentResult.rawText}")
            
            // RTC 연결 시작 (추후 구현)
            // rtcRepository.startConnection(...)
            
            return DispatchResult.Success(
                type = IntentType.OPERATOR,
                message = "RTC 연결 시작",
                data = intentResult.rawText
            )
        } catch (e: Exception) {
            Log.e(TAG, "❌ RTC Start 실패: ${e.message}")
            return DispatchResult.Error("RTC 연결 실패: ${e.message}")
        }
    }

    /**
     * AI Supporter Intent 처리
     * RAG API 호출하여 Clarify 또는 최종 답변을 받습니다.
     */
    private suspend fun handleAiSupporterIntent(intentResult: IntentClassificationDto): DispatchResult {
        return try {
            Log.i(TAG, "🤖 AI Supporter Intent 처리: ${intentResult.rawText}")

            // 1) CV로 에러 상황 추출 시도 (선택사항)
            val cvSummary: String? = tryExtractErrorFromCv(intentResult.rawText)

            // 2) CV 결과에 따라 쿼리 결정
            val queryForRag = if (cvSummary.isNullOrBlank()) {
                Log.i(TAG, "ℹ️ CV 미검출 → 원본 텍스트 사용")
                intentResult.rawText
            } else {
                Log.i(TAG, "✅ CV 검출 성공 → 에러 요약 사용")
                cvSummary
            }

            // 3) 세션 ID 생성 또는 가져오기
            val sessionId = sessionManager.getOrCreateSessionId()
            Log.d(TAG, "📝 세션 ID: $sessionId")

            // 4) RAG API 호출
            val ragResponse = callRagLlm(queryForRag, sessionId)

            // 5) 응답 타입 판단
            if (ragResponse.need_clarify == true) {
                // Clarify 응답
                val clarifyGuidance = ragResponse.clarify_guidance ?: ragResponse.ask ?: ""
                Log.i(TAG, "💬 Clarify 필요: $clarifyGuidance")
                
                DispatchResult.Success(
                    type = IntentType.AI_SUPPORTER,
                    message = "Clarify 필요",
                    data = clarifyGuidance,
                    isClarifyNeeded = true,
                    options = ragResponse.options
                )
            } else {
                // 최종 답변
                val answer = ragResponse.result?.answer ?: ""
                Log.i(TAG, "✅ 최종 답변 수신: $answer")
                
                DispatchResult.Success(
                    type = IntentType.AI_SUPPORTER,
                    message = "최종 답변",
                    data = answer,
                    isClarifyNeeded = false,
                    audioContent = ragResponse.result?.audio_content,
                    audioEncoding = ragResponse.result?.audio_encoding,
                    mimeType = ragResponse.result?.mime_type
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "❌ AI Supporter 처리 실패: ${e.message}")
            DispatchResult.Error("AI Supporter 처리 실패: ${e.message}")
        }
    }

    /**
     * CV API 호출 - 에러 상황 추출 시도
     * Python YOLOv11nano API 호출
     * 
     * @return 에러 상황 요약 (성공 시) 또는 null (실패 시)
     */
    private suspend fun tryExtractErrorFromCv(contextText: String): String? {
        if (detectObjectUseCase == null) {
            Log.w(TAG, "⚠️ DetectObjectUseCase가 주입되지 않음 - CV API 호출 스킵")
            return null
        }
        
        return try {
            Log.d(TAG, "📡 CV API 호출 중...")
            // TODO: DetectObjectUseCase의 실제 API 호출 메서드 확인 후 연동
            // val cvResult = detectObjectUseCase.detectError(...)
            // cvResult?.errorSummary ?: null
            null  // 임시: 실제 API 연동 전까지 null
        } catch (e: Exception) {
            Log.e(TAG, "❌ CV API 호출 실패: ${e.message}")
            null
        }
    }

    /**
     * 서버 RAG + LLM API 호출
     * FastAPI 서버로 전송 (서버에서 EC2로 전달)
     * 
     * @param query 사용자 질문 또는 CV로 추출한 에러 상황
     * @param sessionId 세션 ID (Clarify 루프 동안 동일 ID 유지)
     * @return RAG 응답
     */
    private suspend fun callRagLlm(query: String, sessionId: String): RagResponse {
        if (llmRepository == null) {
            Log.w(TAG, "⚠️ LlmRepository가 주입되지 않음")
            throw IllegalStateException("LlmRepository가 필요합니다")
        }
        
        return try {
            Log.d(TAG, "📡 RAG Chat API 호출 중: query=$query, sessionId=$sessionId")
            llmRepository.generateRagResponse(query, sessionId)
        } catch (e: Exception) {
            Log.e(TAG, "❌ RAG Chat API 호출 실패: ${e.message}")
            throw e
        }
    }
}

/**
 * Intent 분기 처리 결과
 */
sealed class DispatchResult {
    data class Success(
        val type: IntentType,
        val message: String,
        val data: String,
        val isClarifyNeeded: Boolean = false,
        val options: List<String>? = null,
        val audioContent: String? = null,      // Base64 인코딩된 오디오
        val audioEncoding: String? = null,
        val mimeType: String? = null
    ) : DispatchResult()
    
    data class Error(
        val message: String
    ) : DispatchResult()
}

