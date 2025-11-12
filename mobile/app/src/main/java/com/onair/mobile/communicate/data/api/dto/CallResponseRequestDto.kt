package com.onair.mobile.communicate.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class CallResponseRequestDto(
    val acceptConnection: Boolean,
    val senderAccountId: Long,
    val senderName: String
)