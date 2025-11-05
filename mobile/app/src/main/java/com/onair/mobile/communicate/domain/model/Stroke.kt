package com.onair.mobile.communicate.domain.model

data class Stroke(
    val points: List<Point>,
    val tool: String
)

data class Point(
    val x: Double,
    val y: Double
)