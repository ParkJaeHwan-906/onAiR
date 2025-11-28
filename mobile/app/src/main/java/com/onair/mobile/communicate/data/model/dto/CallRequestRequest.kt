package com.onair.mobile.communicate.data.model.dto

import kotlinx.serialization.Serializable

@Serializable
data class CallRequestRequest(
    val receiverAccountId: Long
)