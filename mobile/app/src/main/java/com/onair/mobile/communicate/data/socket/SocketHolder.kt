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
            onCvDetectionFailed = { },
            onClarifyQaTurn = { },
            onWakewordDetected = { },
            onConnect = { },
            onDisconnect = { },
            onConnectError = { }
        )
    }
}
