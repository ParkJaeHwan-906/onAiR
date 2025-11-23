package com.onair.mobile.communicate.data.socket.dto

import kotlinx.serialization.Serializable

@Serializable
data class Citation(
    val excerpt: String,
    val pages: String,
    val section: String
)