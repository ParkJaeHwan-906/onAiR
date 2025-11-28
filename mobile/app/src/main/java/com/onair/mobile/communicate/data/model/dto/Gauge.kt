package com.onair.mobile.communicate.data.model.dto

data class Gauge(
    val detail: String,
    val message: String,
    val results: Results,
    val status: String
)