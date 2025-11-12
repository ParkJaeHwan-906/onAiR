package com.onair.mobile.communicate.data.api.dto

data class CallRequestDto(
    val companyId: Long,
    val description: String,
    val equipmentCategoryId: Long,
    val equipmentCategoryName: String,
    val equipmentId: Long,
    val equipmentName: String,
    val name: String,
    val phone: String,
    val role: String,
    val senderAccountId: Long
)