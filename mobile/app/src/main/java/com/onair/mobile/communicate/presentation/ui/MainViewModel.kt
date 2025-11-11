package com.onair.mobile.communicate.presentation.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onair.mobile.communicate.data.AuthRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class MainViewModel(
    private val authRepository: AuthRepository
): ViewModel() {
    private val _isLoading = MutableStateFlow(true)
    val isLoading = _isLoading.asStateFlow()
    private val _navigationNext = MutableStateFlow<NavigationNext>(NavigationNext.LOADING)
    val navigationNext = _navigationNext.asStateFlow()
    init {
        checkTokenStatus()
    }
    private fun checkTokenStatus() {
        viewModelScope.launch {
            val refreshToken = authRepository.getRefreshToken()
            if (refreshToken.isEmpty()) {
                _navigationNext.value = NavigationNext.LOGIN
            } else {
                authRepository.refreshAccessToken(refreshToken) { result ->
                    result.onSuccess {
                        _navigationNext.value = NavigationNext.MAIN
                    }.onFailure { e ->
                        _navigationNext.value = NavigationNext.LOGIN
                    }
                }
            }
            _isLoading.value = false
        }
    }
}

sealed class NavigationNext {
    object LOADING : NavigationNext()
    object MAIN : NavigationNext()
    object LOGIN : NavigationNext()
}