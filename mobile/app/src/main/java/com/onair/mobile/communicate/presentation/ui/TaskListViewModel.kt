package com.onair.mobile.communicate.presentation.ui

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.onair.mobile.communicate.data.TaskRepository
import com.onair.mobile.communicate.data.api.ApiClient
import com.onair.mobile.communicate.data.api.dto.TaskResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class TaskListViewModel(
    private val taskRepository: TaskRepository
) : ViewModel() {
    private val _taskState = MutableStateFlow<String>("todo")
    val taskState : StateFlow<String> = _taskState
    private val _taskList = MutableStateFlow<List<TaskResponse>>(emptyList())
    val taskList = _taskList.asStateFlow()
    val incompletedTask = _taskList.map { list ->
        list.filter { it.action != 3 }
    }.stateIn(viewModelScope, SharingStarted.Lazily, emptyList())
    val completedTask = _taskList.map { list ->
        list.filter { it.action == 3 }
    }.stateIn(viewModelScope, SharingStarted.Lazily, emptyList())

    init {
        getTaskList()
    }
    fun getTaskList() {
        viewModelScope.launch {
            taskRepository.getTaskList() { result ->
                result.onSuccess { list ->
                    _taskList.value = list
                }.onFailure { exception ->
                    _taskList.value = emptyList<TaskResponse>()
                }
            }
        }
    }
}