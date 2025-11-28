package com.onair.mobile.communicate.data.model.dto

import kotlinx.serialization.Serializable

@Serializable
data class EndTaskRequest(
    val solution: String,
    val taskId: Long
)