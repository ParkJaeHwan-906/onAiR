package com.onair.mobile.communicate.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class RecommendedAction(
    val action: String,
    val priority: String
)