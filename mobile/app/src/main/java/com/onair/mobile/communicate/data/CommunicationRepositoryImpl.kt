package com.onair.mobile.communicate.data

import com.onair.mobile.communicate.data.api.ApiService
import com.onair.mobile.communicate.domain.model.Stroke
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow

//class CommunicationRepositoryImpl : CommunicationRepository {
//
//    private val _lineFlow = MutableSharedFlow<List<Stroke>>(replay = 1)
//    override fun observeLines(): Flow<List<Stroke>> = _lineFlow.asSharedFlow()
//
//    fun onRemoteLineReceived(lines: List<Stroke>) {
//        _lineFlow.tryEmit(lines)
//    }
//}

class CommunicationRepositoryImpl(

    private val apiService: ApiService
) {
    fun startSse() {


    }
}