package com.onair.mobile.communicate.presentation.ui

import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import com.onair.mobile.communicate.domain.model.Stroke

class CommunicationViewModel : ViewModel() {
    private val _lines = MutableLiveData<List<Stroke>>()
    val lines: LiveData<List<Stroke>> get() = _lines

//    fun getLines()

}