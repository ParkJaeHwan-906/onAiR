package com.onair.mobile.communicate.data.api.dto

data class CvDetectionResult(
    val anomalies: Anomalies,
    val device_type: String,
    val message: String,
    val modules: List<String>
)