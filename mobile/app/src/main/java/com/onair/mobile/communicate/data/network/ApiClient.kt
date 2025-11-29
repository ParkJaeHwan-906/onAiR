package com.onair.mobile.communicate.data.network

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

object ApiClient {
    private const val SPRING_BASE_URL = "https://onair.ai.kr/api/"
    private const val FAST_API_BASE_URL = "https://onair.ai.kr/ai/"

    private val okHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .addInterceptor(TokenInterceptor())
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        })
        .build()

    val springRetrofit : Retrofit = Retrofit.Builder()
        .baseUrl(SPRING_BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(
            Json.Default.asConverterFactory(
                "application/json".toMediaType()))
        .build()

    val fastApiRetrofit: Retrofit = Retrofit.Builder()
        .baseUrl(FAST_API_BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(
            Json.Default.asConverterFactory(
                "application/json".toMediaType()))
        .build()


//    fun getSpringRetrofit(): Retrofit { return springRetrofit }
//    fun getFastApiRetrofit(): Retrofit { return fastApiRetrofit }
    fun getOkHttpClient(): OkHttpClient { return okHttpClient }
}