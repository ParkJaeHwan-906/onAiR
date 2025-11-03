package com.onair.mobile.assistant.data.intent

import android.content.Context
import android.util.Log
import ai.onnxruntime.*
import com.onair.mobile.assistant.core.model.dto.IntentClassificationDto
import com.onair.mobile.assistant.domain.entity.IntentType
import java.nio.FloatBuffer
import java.nio.IntBuffer

/**
 * ONNX Runtime을 사용한 Intent Classifier
 * 
 * 모델 경로: assets/models/intent_classifier.int8.onnx
 */
class OnnxIntentClassifierDataSource(private val context: Context) {

    private val TAG = "OnnxIntentClassifier"
    private val MODEL_PATH = "models/intent_classifier.int8.onnx"
    
    private var ortEnv: OrtEnvironment? = null
    private var ortSession: OrtSession? = null
    private var isInitialized = false

    /**
     * 모델 초기화
     */
    fun init() {
        if (isInitialized) {
            Log.w(TAG, "⚠️ 이미 초기화되어 있습니다")
            return
        }

        try {
            ortEnv = OrtEnvironment.getEnvironment()
            
            // Assets에서 모델 파일 읽기
            val modelBytes = context.assets.open(MODEL_PATH).use { input ->
                input.readBytes()
            }
            
            // ONNX Runtime 세션 생성
            ortSession = ortEnv!!.createSession(modelBytes)
            
            isInitialized = true
            Log.i(TAG, "✅ Intent Classifier 모델 로드 완료")
            
            // 모델 입력/출력 정보 로깅
            logModelInfo()
            
        } catch (e: Exception) {
            Log.e(TAG, "❌ 모델 로드 실패: ${e.message}")
            e.printStackTrace()
            throw IllegalStateException("Intent Classifier 초기화 실패", e)
        }
    }

    /**
     * 모델 정보 로깅
     */
    private fun logModelInfo() {
        try {
            ortSession?.let { session ->
                Log.d(TAG, "📊 모델 입력: ${session.inputNames.joinToString()}")
                Log.d(TAG, "📊 모델 출력: ${session.outputNames.joinToString()}")
            }
        } catch (e: Exception) {
            Log.w(TAG, "⚠️ 모델 정보 로깅 실패: ${e.message}")
        }
    }

    /**
     * 텍스트를 Intent로 분류
     * 
     * @param text 입력 텍스트
     * @return Intent 분류 결과
     */
    fun classify(text: String): IntentClassificationDto {
        if (!isInitialized || ortSession == null) {
            Log.e(TAG, "❌ 모델이 초기화되지 않았습니다")
            return IntentClassificationDto(
                intentType = IntentType.UNKNOWN,
                confidence = 0.0f,
                rawText = text
            )
        }

        try {
            // 텍스트를 임베딩으로 변환 (간단한 방식)
            // TODO: 실제 텍스트 토크나이저/임베딩 필요
            val embeddings = textToEmbeddings(text)
            
            // ONNX 모델 입력 준비
            val inputTensor = createInputTensor(embeddings)
            
            // 추론 실행
            val outputs = ortSession!!.run(mapOf("embeddings" to inputTensor))
            
            // 결과 파싱
            val result = parseOutput(outputs)
            
            Log.d(TAG, "🧠 Intent 분류 결과: ${result.intentType} (${result.confidence})")
            
            // Tensor 정리
            inputTensor.close()
            outputs.close()
            
            return result.copy(rawText = text)
            
        } catch (e: Exception) {
            Log.e(TAG, "❌ Intent 분류 실패: ${e.message}")
            e.printStackTrace()
            return IntentClassificationDto(
                intentType = IntentType.UNKNOWN,
                confidence = 0.0f,
                rawText = text
            )
        }
    }

    /**
     * 텍스트를 임베딩 벡터로 변환 (간단한 방식)
     * TODO: 실제 토크나이저/임베딩 모델 사용 필요
     */
    private fun textToEmbeddings(text: String): FloatArray {
        // 간단한 해시 기반 임베딩 (실제로는 토크나이저 필요)
        val embeddingSize = 384  // 모델에 맞게 조정
        val embeddings = FloatArray(embeddingSize)
        
        // 간단한 해시 기반 변환
        for (i in text.indices) {
            val char = text[i]
            val index = (char.code % embeddingSize)
            embeddings[index] += 0.1f
        }
        
        // 정규화
        val sum = embeddings.sum()
        if (sum > 0) {
            for (i in embeddings.indices) {
                embeddings[i] /= sum
            }
        }
        
        return embeddings
    }

    /**
     * ONNX 입력 Tensor 생성
     */
    private fun createInputTensor(embeddings: FloatArray): OnnxTensor {
        val shape = longArrayOf(1, embeddings.size.toLong())  // [batch, embedding_size]
        return OnnxTensor.createTensor(ortEnv!!, FloatBuffer.wrap(embeddings), shape)
    }

    /**
     * 모델 출력 파싱
     */
    private fun parseOutput(outputs: OrtSession.Result): IntentClassificationDto {
        // logits 출력 가져오기
        val logitsValue = outputs.get(0) ?: throw IllegalStateException("logits 출력을 찾을 수 없습니다")
        
        val logitsTensor = logitsValue.value as Array<FloatArray>
        
        if (logitsTensor.isEmpty() || logitsTensor[0].isEmpty()) {
            return IntentClassificationDto(
                intentType = IntentType.UNKNOWN,
                confidence = 0.0f,
                rawText = ""
            )
        }

        // 가장 높은 점수의 Intent 선택
        val scores = logitsTensor[0]
        var maxIndex = 0
        var maxScore = scores[0]

        for (i in scores.indices) {
            if (scores[i] > maxScore) {
                maxScore = scores[i]
                maxIndex = i
            }
        }

        // 인덱스를 IntentType으로 매핑
        // 모델 출력: 0 = OPERATOR, 1 = AI_SUPPORTER
        val intentType = when (maxIndex) {
            0 -> IntentType.OPERATOR
            1 -> IntentType.AI_SUPPORTER
            else -> IntentType.UNKNOWN
        }

        // Confidence 계산 (소프트맥스 적용)
        val confidence = calculateConfidence(scores, maxIndex)

        return IntentClassificationDto(
            intentType = intentType,
            confidence = confidence,
            rawText = ""
        )
    }

    /**
     * 소프트맥스를 적용한 Confidence 계산
     */
    private fun calculateConfidence(scores: FloatArray, index: Int): Float {
        // 간단한 소프트맥스
        val expScores = scores.map { kotlin.math.exp(it) }
        val sumExp = expScores.sum()
        
        return if (sumExp > 0) {
            (expScores[index] / sumExp).toFloat()
        } else {
            0.0f
        }
    }

    /**
     * 리소스 정리
     */
    fun cleanup() {
        try {
            ortSession?.close()
            ortEnv?.close()
            isInitialized = false
            Log.i(TAG, "🗑️ Intent Classifier 리소스 정리 완료")
        } catch (e: Exception) {
            Log.e(TAG, "❌ 리소스 정리 실패: ${e.message}")
        }
    }
}

