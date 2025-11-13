package com.onair.mobile.communicate.data.sse

import android.content.Context
import com.launchdarkly.eventsource.ConnectStrategy
import com.launchdarkly.eventsource.EventSource
import com.launchdarkly.eventsource.background.BackgroundEventHandler
import com.launchdarkly.eventsource.background.BackgroundEventSource
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import okhttp3.Dispatcher
import okhttp3.OkHttpClient
import java.net.URI
import java.net.URL
import java.util.concurrent.TimeUnit

class SseClient(
    private val okHttpClient: OkHttpClient,
    private val sseBaseUrl: String
) {
    val sseUrl = "https://onair.ai.kr/api/sse/stream"
//    val accessToken = PreferenceUtil(context).getAccessToken()
    private var backgroundEventSource : BackgroundEventSource? = null
    fun initSSE(eventHandler: BackgroundEventHandler) {
        if (backgroundEventSource == null) {

            backgroundEventSource = BackgroundEventSource.Builder(eventHandler, EventSource.Builder(
                ConnectStrategy
                    .http(URL(sseUrl))
                    .connectTimeout(30, TimeUnit.SECONDS)
                    .readTimeout(600, TimeUnit.SECONDS)
                    .httpClient(okHttpClient)
            ))
                .threadPriority(Thread.MAX_PRIORITY)
                .build()
        }
        backgroundEventSource?.start()
    }
    fun disconnect() {
        backgroundEventSource?.let {
            CoroutineScope(Dispatchers.IO).launch {
                it.close()
                backgroundEventSource = null
            }
        }
    }

}