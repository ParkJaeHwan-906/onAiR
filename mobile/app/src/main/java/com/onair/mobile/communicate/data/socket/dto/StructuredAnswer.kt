package com.onair.mobile.communicate.data.socket.dto

import kotlinx.serialization.Serializable

@Serializable
data class StructuredAnswer(
    val citations: List<Citation>,
    val error_code: String,
    val markdown_text: String,
    val possible_causes: List<Any>,
    val possible_causes_audio: String,
    val possible_causes_audio_encoding: String,
    val possible_causes_markdown: String,
    val query: String,
    val recommended_actions: List<Any>,
    val recommended_actions_audio: String,
    val recommended_actions_audio_encoding: String,
    val recommended_actions_markdown: String,
    val safety_warnings: List<Any>,
    val safety_warnings_audio: String,
    val safety_warnings_audio_encoding: String,
    val safety_warnings_markdown: String,
    val tts_text: String
)