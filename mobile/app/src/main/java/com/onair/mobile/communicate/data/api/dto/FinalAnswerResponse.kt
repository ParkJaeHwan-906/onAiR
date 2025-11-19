package com.onair.mobile.communicate.data.api.dto


data class FinalAnswerResponse(
    val answer: String,
    val audio_content: Any,
    val audio_encoding: Any,
    val citations: List<Citation>,
    val cv_detection_result: CvDetectionResult,
    val session_id: Any,
    val status: String,
    val structured_answer: StructuredAnswer,
    val turn_id: Int
)