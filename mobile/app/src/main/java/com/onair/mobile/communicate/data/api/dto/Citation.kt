package com.onair.mobile.communicate.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class Citation(
    val excerpt: String,
    val pages: List<Int>,
    val section: String
)