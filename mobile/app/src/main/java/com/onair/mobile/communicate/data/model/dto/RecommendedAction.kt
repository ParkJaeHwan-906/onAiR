package com.onair.mobile.communicate.data.model.dto

import kotlinx.serialization.Serializable

@Serializable
data class RecommendedAction(
    val action: String,
    val priority: String
)