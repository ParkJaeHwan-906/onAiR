package com.onair.mobile.communicate.data.source.remote

import com.onair.mobile.assistant.data.stt.SocketIoSttClient

object SocketHolder {
    val socketClient: SocketIoSttClient by lazy {
        SocketIoSttClient(
            serverUrl = "wss://onair.ai.kr",

            onSttResult = { text, type, conf -> },
            onClarifyResponse = { },
            onIntentResult = { },
            onClarifyTurn = { },
            onFinalAnswer = { },
            onStartSseConnection = { },
            onCvDetectionNormal = { },
            onCvDetectionFailed = { },
            onClarifyQaTurn = { },
            onWakewordDetected = { },
            onConnect = { },
            onDisconnect = { },
            onConnectError = { }
        )
    }
}