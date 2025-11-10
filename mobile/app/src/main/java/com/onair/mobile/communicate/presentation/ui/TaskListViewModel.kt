package com.onair.mobile.communicate.presentation.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onair.mobile.communicate.data.TaskRepository
import com.onair.mobile.communicate.data.api.ApiClient
import com.onair.mobile.communicate.data.api.dto.TaskResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class TaskListViewModel(
    private val taskRepository: TaskRepository
) : ViewModel() {
    private val _taskState = MutableStateFlow<String>("todo")
    val taskState : StateFlow<String> = _taskState
    private val _taskList = MutableStateFlow<List<TaskResponse>>(emptyList())
    val taskList = _taskList.asStateFlow()

    fun getTaskList(action: Int) {
        viewModelScope.launch {
            taskRepository.getCompletedTaskList(action) { result ->
                result.onSuccess { list ->
                    _taskList.value = list
                }.onFailure { exception ->
                    _taskList.value = emptyList<TaskResponse>()
                }
            }
        }
    }
}