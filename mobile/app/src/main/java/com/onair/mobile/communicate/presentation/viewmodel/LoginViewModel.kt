package com.onair.mobile.communicate.presentation.viewmodel

import androidx.lifecycle.ViewModel
import com.onair.mobile.communicate.data.AuthRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

class LoginViewModel(
    private val authRepository: AuthRepository
) : ViewModel() {
    private val _loginState = MutableStateFlow<Boolean>(false)
    val loginState = _loginState.asStateFlow()
    private val _errorMassage = MutableStateFlow<String>("")
    val errorMassage = _errorMassage.asStateFlow()

    fun login(email: String, pw: String) {
        authRepository.login(email, pw) { result ->
            result.onSuccess {
                _loginState.value = true
            }.onFailure { e ->
                _loginState.value = false
                _errorMassage.value = e.message.toString()
            }
        }
    }
}