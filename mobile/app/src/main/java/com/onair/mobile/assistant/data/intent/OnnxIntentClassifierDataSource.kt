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
 * 
 * 모델 정보 (노트북 기반):
 * - 입력: embeddings (3072차원) - Phi-3-mini-4k-instruct 임베딩
 * - 출력: logits (2차원) - [OPERATOR, AI_SUPPORTER]
 * - 학습: Phi-3 임베딩 + MLP 분류기 (PyTorch) → ONNX Export
 * 
 * ⚠️ 중요: 모델은 Phi-3 임베딩을 입력으로 받습니다.
 * 현재는 임시 임베딩을 사용 중이며, 실제 배포 시 Phi-3 임베딩이 필요합니다.
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
                val inputNames = session.inputNames
                val outputNames = session.outputNames
                
                Log.i(TAG, "📊 모델 입력 이름: ${inputNames.joinToString()}")
                Log.i(TAG, "📊 모델 출력 이름: ${outputNames.joinToString()}")
                
                // 입력 메타데이터 확인
                inputNames.forEach { inputName ->
                    try {
                        val inputInfo = session.inputInfo[inputName]
                        Log.i(TAG, "📊 입력 '$inputName' 정보: $inputInfo")
                    } catch (e: Exception) {
                        Log.w(TAG, "⚠️ 입력 '$inputName' 정보 조회 실패: ${e.message}")
                    }
                }
                
                // 출력 메타데이터 확인
                outputNames.forEach { outputName ->
                    try {
                        val outputInfo = session.outputInfo[outputName]
                        Log.i(TAG, "📊 출력 '$outputName' 정보: $outputInfo")
                    } catch (e: Exception) {
                        Log.w(TAG, "⚠️ 출력 '$outputName' 정보 조회 실패: ${e.message}")
                    }
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "⚠️ 모델 정보 로깅 실패: ${e.message}")
        }
    }

    /**
     * 텍스트를 Intent로 분류
     * 
     * ⚠️ Deprecated: 이 메서드는 임시 구현입니다.
     * 실제 배포 시에는 classifyWithEmbedding()을 사용하세요.
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
            
            return classifyWithEmbedding(embeddings, text)
            
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
     * Phi-3 임베딩을 받아서 Intent로 분류
     * 
     * FastAPI 서버로부터 받은 3072차원 임베딩 벡터를 분류합니다.
     * 
     * @param embedding 3072차원 FloatArray (Phi-3 임베딩)
     * @param rawText 원본 텍스트 (로그/디버깅용)
     * @return Intent 분류 결과
     */
    fun classifyWithEmbedding(embedding: FloatArray, rawText: String = ""): IntentClassificationDto {
        if (!isInitialized || ortSession == null) {
            Log.e(TAG, "❌ 모델이 초기화되지 않았습니다")
            return IntentClassificationDto(
                intentType = IntentType.UNKNOWN,
                confidence = 0.0f,
                rawText = rawText
            )
        }

        try {
            // 임베딩 차원 검증
            if (embedding.size != 3072) {
                Log.e(TAG, "❌ 임베딩 차원 불일치: 예상 3072, 실제 ${embedding.size}")
                return IntentClassificationDto(
                    intentType = IntentType.UNKNOWN,
                    confidence = 0.0f,
                    rawText = rawText
                )
            }
            
            // ONNX 모델 입력 준비
            val inputName = ortSession!!.inputNames.firstOrNull() 
                ?: throw IllegalStateException("모델 입력 이름을 찾을 수 없습니다")
            
            val inputTensor = createInputTensor(embedding)
            
            // 추론 실행
            val outputs = ortSession!!.run(mapOf(inputName to inputTensor))
            
            // 결과 파싱
            val result = parseOutput(outputs)
            
            Log.d(TAG, "🧠 Intent 분류 결과: ${result.intentType} (${result.confidence})")
            
            // Tensor 정리
            inputTensor.close()
            outputs.close()
            
            return result.copy(rawText = rawText)
            
        } catch (e: Exception) {
            Log.e(TAG, "❌ Intent 분류 실패: ${e.message}")
            e.printStackTrace()
            return IntentClassificationDto(
                intentType = IntentType.UNKNOWN,
                confidence = 0.0f,
                rawText = rawText
            )
        }
    }

    /**
     * 텍스트를 임베딩 벡터로 변환
     * 
     * 노트북 학습 시 사용한 방식:
     * - Phi-3-mini-4k-instruct 모델 사용
     * - 토크나이저로 토큰화 → Phi-3 모델 → last_hidden_state.mean(dim=1)
     * - 출력: 3072차원 FloatArray
     * 
     * ⚠️ 주의: 안드로이드에서 Phi-3 전체 모델 실행은 비현실적 (모델 크기 ~7GB)
     * 
     * 옵션:
     * 1. 서버에서 Phi-3 임베딩 추출 후 안드로이드로 전송
     * 2. 경량 임베딩 모델 사용 (예: SentenceTransformer 경량 버전)
     * 3. 임시로 간단한 임베딩 사용 (테스트용, 성능 저하 예상)
     * 
     * 현재는 임시 구현입니다. 실제 배포 시 Phi-3 임베딩이 필요합니다.
     */
    private fun textToEmbeddings(text: String): FloatArray {
        // TODO: 실제 Phi-3 임베딩 필요
        // 노트북의 embed_batch 함수와 동일한 방식으로 임베딩 추출 필요
        
        // 임시 구현: 3072차원으로 맞춤 (모델 입력 크기)
        val embeddingSize = 3072  // Phi-3 hidden_dim
        
        // 간단한 해시 기반 임베딩 (임시, 실제 성능은 낮을 수 있음)
        val embeddings = FloatArray(embeddingSize)
        
        // 텍스트를 문자 단위로 해시하여 임베딩 생성
        for (i in text.indices) {
            val char = text[i]
            val hash = char.code
            val index = (hash % embeddingSize + embeddingSize) % embeddingSize
            embeddings[index] += 0.1f
        }
        
        // 정규화
        val sum = embeddings.sum()
        if (sum > 0) {
            for (i in embeddings.indices) {
                embeddings[i] /= sum
            }
        }
        
        Log.w(TAG, "⚠️ 임시 임베딩 사용 중: 실제 Phi-3 임베딩이 필요합니다")
        
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
        // 노트북의 LabelEncoder: ['AI_SUPPORT', 'OPERATOR']
        // 따라서: 0 = AI_SUPPORT, 1 = OPERATOR
        val intentType = when (maxIndex) {
            0 -> IntentType.AI_SUPPORTER  // AI_SUPPORT → AI_SUPPORTER
            1 -> IntentType.OPERATOR
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

