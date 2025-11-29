package com.onair.mobile.communicate.data.network

import com.onair.mobile.communicate.PreferenceUtil
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response

class TokenInterceptor(): Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val noAuthHeader = originalRequest.header("NO_AUTH")

        if (noAuthHeader != null) {
            val request = originalRequest.newBuilder()
                .removeHeader("NO_AUTH")
                .build()
            return chain.proceed(request)
        } else {
            val accessToken = runBlocking { PreferenceUtil.getAccessToken() }
            val request = originalRequest.newBuilder()
                .addHeader("Authorization", "Bearer $accessToken")
                .build()
            return chain.proceed(request)
        }
    }
}