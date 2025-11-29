package com.onair.mobile.communicate.data.model.dto

import kotlinx.serialization.Serializable

@Serializable
data class TaskResponse(
    val action: Int,
    val actionStatus: String?,
    val equipmentId: Long,
    val equipmentName: String,
    val id: Long,
    val lastUpdateTime: String,
    val request: String,
    val solution: String?,
    val userAccountId: Long,
    val userName: String
)