package com.onair.mobile.communicate.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class RtcResponse (
    val accessToken: String
)