package com.onair.mobile.communicate.data.socket.dto

import kotlinx.serialization.Serializable

@Serializable
data class VideoFrameResponse(
    val timestamp: Long,
    val frame: String
)
