package com.onair.mobile.communicate.data.api.dto

data class Gauge(
    val detail: String,
    val message: String,
    val results: Results,
    val status: String
)