package com.onair.mobile.communicate.presentation.ui

import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onair.mobile.communicate.data.CommunicationRepository
import com.onair.mobile.communicate.data.SSERepository
import com.onair.mobile.communicate.domain.model.Point
import com.onair.mobile.communicate.domain.model.Stroke
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class CommunicationViewModel(
//    private val repo: CommunicationRepository
    private val repo: SSERepository
)
    : ViewModel() {
        val eventFlow = repo.eventFlow
//    private val _lines = MutableStateFlow<List<Stroke>>(emptyList())
//    val lines : StateFlow<List<Stroke>> = _lines
//
//    init {
//        viewModelScope.launch {
//            repo.observeLines().collect { newLines ->
//                _lines.value = newLines
//            }
//        }
//    }
    fun startSSE() {
        repo.startSSE()
    }
    fun stopSSE() {
        repo.stopSSE()
    }

//    fun getLines()

}