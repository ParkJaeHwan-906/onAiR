package com.onair.mobile.assistant.core.common

/**
 * 결과를 나타내는 sealed class
 * 성공 또는 실패를 나타냄
 */
sealed class Result<out T> {
    /**
     * 성공 결과
     */
    data class Success<out T>(val data: T) : Result<T>()
    
    /**
     * 실패 결과
     */
    data class Error(val exception: Exception) : Result<Nothing>()
    
    /**
     * 결과가 성공인지 확인
     */
    val isSuccess: Boolean
        get() = this is Success
    
    /**
     * 결과가 실패인지 확인
     */
    val isError: Boolean
        get() = this is Error
    
    /**
     * 성공 시 데이터 반환, 실패 시 null
     */
    fun getOrNull(): T? = when (this) {
        is Success -> data
        is Error -> null
    }
    
    /**
     * 성공 시 데이터 반환, 실패 시 기본값 반환
     */
    fun getOrDefault(defaultValue: @UnsafeVariance T): T = when (this) {
        is Success -> data
        is Error -> defaultValue
    }
}

