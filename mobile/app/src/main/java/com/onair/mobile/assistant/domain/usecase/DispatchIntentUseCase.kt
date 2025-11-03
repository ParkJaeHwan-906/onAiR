package com.onair.mobile.assistant.domain.usecase

import android.util.Log
import com.onair.mobile.assistant.core.model.dto.IntentClassificationDto
import com.onair.mobile.assistant.domain.entity.IntentType
import com.onair.mobile.assistant.domain.repository.LlmRepository

/**
 * Intent 분류 결과에 따라 적절한 처리 경로로 분기하는 UseCase
 * 
 * 플로우:
 * - OPERATOR → RTC Start
 * - AI_SUPPORTER → CV API 호출 → (성공 시 에러 상황 or 실패 시 Clarification) → 서버 RAG+LLM API 호출
 */
class DispatchIntentUseCase(
    private val detectObjectUseCase: DetectObjectUseCase? = null,
    private val clarifyQuestionUseCase: ClarifyQuestionUseCase? = null,
    private val llmRepository: LlmRepository? = null
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
     * Vision Analyzer로 에러 상황 추출을 시도하고, 성공/실패와 무관하게
     * 최종적으로 서버 RAG+LLM을 호출한다.
     */
    private suspend fun handleAiSupporterIntent(intentResult: IntentClassificationDto): DispatchResult {
        return try {
            Log.i(TAG, "🔍 Vision Analyzer 호출 준비: ${intentResult.rawText}")

            // 1) CV로 에러 상황 추출 시도 (성공/실패 모두 허용)
            val cvSummary: String? = tryExtractErrorFromCv(intentResult.rawText)

            // 2) CV 실패 또는 미검출 시 Clarification으로 질의 보강
            val queryForRag = if (cvSummary.isNullOrBlank()) {
                Log.i(TAG, "ℹ️ CV 미검출 → Clarification 수행")
                buildClarifiedQuery(intentResult.rawText)
            } else {
                Log.i(TAG, "✅ CV 검출 성공 → 에러 요약 사용")
                cvSummary
            }

            // 3) 서버 RAG + LLM 호출 (단일 진입점)
            val ragAnswer = callRagLlm(queryForRag)

            Log.i(TAG, "🧠 RAG+LLM 응답 수신: $ragAnswer")

            DispatchResult.Success(
                type = IntentType.AI_SUPPORTER,
                message = "AI Supporter 처리 완료",
                data = ragAnswer
            )
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
     * Clarification Model API 호출 - 질의 구체화
     * 
     * @return 구체화된 질문 1개
     */
    private suspend fun buildClarifiedQuery(originalText: String): String {
        if (clarifyQuestionUseCase == null) {
            Log.w(TAG, "⚠️ ClarifyQuestionUseCase가 주입되지 않음 - 원본 텍스트 반환")
            return originalText
        }
        
        return try {
            Log.d(TAG, "📡 Clarification API 호출 중...")
            // TODO: ClarifyQuestionUseCase의 실제 API 호출 메서드 확인 후 연동
            // val clarified = clarifyQuestionUseCase.clarify(originalText)
            // clarified.clarifiedQuestion
            originalText  // 임시: 실제 API 연동 전까지 원본 반환
        } catch (e: Exception) {
            Log.e(TAG, "❌ Clarification API 호출 실패: ${e.message}")
            originalText  // 실패 시 원본 텍스트 반환
        }
    }

    /**
     * 서버 RAG + LLM API 호출
     * FastAPI 서버로 전송 (서버에서 EC2로 전달)
     * 
     * @param query CV로 추출한 에러 상황 또는 Clarification으로 구체화된 질문
     * @return RAG+LLM 응답 텍스트
     */
    private suspend fun callRagLlm(query: String): String {
        if (llmRepository == null) {
            Log.w(TAG, "⚠️ LlmRepository가 주입되지 않음")
            throw IllegalStateException("LlmRepository가 필요합니다")
        }
        
        return try {
            Log.d(TAG, "📡 서버 RAG+LLM API 호출 중: $query")
            // TODO: LlmRepository의 실제 API 호출 메서드 확인 후 연동
            // val response = llmRepository.generateRagResponse(query)
            // response.answer
            throw IllegalStateException("RAG+LLM API 연동 필요")
        } catch (e: Exception) {
            Log.e(TAG, "❌ RAG+LLM API 호출 실패: ${e.message}")
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
        val data: String
    ) : DispatchResult()
    
    data class Error(
        val message: String
    ) : DispatchResult()
}

