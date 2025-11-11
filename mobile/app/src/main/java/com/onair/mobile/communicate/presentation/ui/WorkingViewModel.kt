package com.onair.mobile.communicate.presentation.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onair.mobile.communicate.data.TaskRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class WorkingViewModel(
    private val repository: TaskRepository
): ViewModel() {
    private val _endStatus = MutableStateFlow(false)
    val endStatus = _endStatus.asStateFlow()



    fun endTask(taskId: Long, solution: String) {
        viewModelScope.launch {
            repository.endTask(taskId, solution) { result ->
                result.onSuccess {
                    _endStatus.value = true
                }.onFailure {

                }
            }
        }
    }
}