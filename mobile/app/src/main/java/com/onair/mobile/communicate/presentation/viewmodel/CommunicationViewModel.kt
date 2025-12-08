package com.onair.mobile.communicate.presentation.viewmodel

import androidx.lifecycle.ViewModel
import com.onair.mobile.communicate.data.SSERepository

class CommunicationViewModel(
    private val repo: SSERepository
) : ViewModel() {
        val eventFlow = repo.eventFlow
    fun startSSE() {
        repo.startSSE()
    }
    fun stopSSE() {
        repo.stopSSE()
    }
    fun clearEvent() {
        repo.clearEvent()
    }
}