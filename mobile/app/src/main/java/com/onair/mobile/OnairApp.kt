package com.onair.mobile

import android.app.Application
import android.content.Context
import android.util.Log
import com.onair.mobile.communicate.data.SSERepository
import com.onair.mobile.communicate.data.network.ApiClient
import com.onair.mobile.communicate.data.network.SseClient
import com.onair.mobile.communicate.presentation.viewmodel.CommunicationViewModel
import kotlin.time.Instant

class OnairApp : Application() {
    companion object {
        lateinit var instance: OnairApp
            private set

        fun context(): Context {
            return instance.applicationContext
        }
    }
    val sseViewModel: CommunicationViewModel by lazy {
        val okHttpClient = ApiClient.getOkHttpClient()
        val sseRepo = SSERepository(SseClient(okHttpClient, "/task/stream"))
        CommunicationViewModel(sseRepo)
    }

    override fun onCreate() {
        super.onCreate()
        Log.d("OnairApp", "앱 onCreate 실행됨 ✅")
        instance = this

    }
}

