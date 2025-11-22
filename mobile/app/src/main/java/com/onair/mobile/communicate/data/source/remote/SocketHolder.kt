package com.onair.mobile.communicate.data.source.remote

import com.onair.mobile.assistant.data.stt.SocketIoSttClient

object SocketHolder {
    val socketClient: SocketIoSttClient by lazy {
        SocketIoSttClient(
            serverUrl = "wss://onair.ai.kr",

            onSttResult = { text, type, conf -> },
            onIntentResult = { },
            onFinalAnswer = { },
            onStartSseConnection = { },
            onCvDetectionNormal = { },
            onCvDetectionFailed = { },
            onWakewordDetected = { },
            onConnect = { },
            onDisconnect = { },
            onConnectError = { }
        )
    }
}