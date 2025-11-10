package com.onair.mobile.communicate.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class TaskResponse(
    val action: Int,
    val actionStatus: String,
    val equipmentId: Int,
    val equipmentName: String,
    val id: Int,
    val lastUpdateTime: String,
    val request: String,
    val solution: String,
    val userAccountId: Int,
    val userName: String
)