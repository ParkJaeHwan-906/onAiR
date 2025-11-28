package com.onair.mobile.communicate.data.model.dto

import kotlinx.serialization.Serializable

@Serializable
data class RefreshRequest(
    val refreshToken : String
)
