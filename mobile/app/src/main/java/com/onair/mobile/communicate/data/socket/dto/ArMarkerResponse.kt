package com.onair.mobile.communicate.data.socket.dto

import kotlinx.serialization.Serializable

@Serializable
data class ArMarkerResponse(
    val markers: List<ArMarker>
)

@Serializable
data class ArMarker(
    val type: String,
    val idx: Int,
    val info: MarkerInfo,
    val color : String?,
    val pulseScale: Float?,
    val pulseOpacity: Float?,
    val opacity: Float?
)

@Serializable
data class MarkerInfo(
    val size: Float,
    val x: Float,
    val y: Float,
)