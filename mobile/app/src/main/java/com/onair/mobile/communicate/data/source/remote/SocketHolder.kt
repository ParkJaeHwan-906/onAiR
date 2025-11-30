package com.onair.mobile.communicate.data.source.remote

import com.onair.mobile.communicate.data.network.SocketIoSttClient

object SocketHolder {
    val socketClient: SocketIoSttClient by lazy {
        SocketIoSttClient(
            serverUrl = "wss://onair.ai.kr",

            onSttResult = { text, type, conf -> },
            onIntentResult = { },
            onCvDetectionNormal = { },
            onCvDetectionFailed = { },
            onWakewordDetected = { },
            onConnect = { },
            onDisconnect = { },
            onConnectError = { }
        )
    }
}