package com.onair.mobile.communicate.data

import com.onair.mobile.communicate.domain.model.Stroke
import kotlinx.coroutines.flow.Flow

interface CommunicationRepository {
    fun observeLines(): Flow<List<Stroke>>
}