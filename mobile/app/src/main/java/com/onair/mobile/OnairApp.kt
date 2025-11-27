package com.onair.mobile

import android.app.Application
import android.util.Log
import com.onair.mobile.communicate.data.SSERepository
import com.onair.mobile.communicate.data.api.ApiClient
import com.onair.mobile.communicate.data.source.remote.SseClient
import com.onair.mobile.communicate.presentation.viewmodel.CommunicationViewModel
class OnairApp : Application() {
    val sseViewModel: CommunicationViewModel by lazy {
        val okHttpClient = ApiClient(this).getOkHttpClient()
        val sseRepo = SSERepository(SseClient(okHttpClient, "/task/stream"))
        CommunicationViewModel(sseRepo)
    }

    override fun onCreate() {
        super.onCreate()
        Log.d("OnairApp", "앱 onCreate 실행됨 ✅")
    }
}

