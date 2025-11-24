package com.onair.mobile.communicate.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class CallRequestRequest(
    val receiverAccountId: Long
)