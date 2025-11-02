package com.onair.mobile.communicate.utils

import com.onair.mobile.communicate.data.CommunicationRepositoryImpl
import com.onair.mobile.communicate.presentation.ui.CommunicationViewModel

object DependencyProvider {
    private val communicationRepository = CommunicationRepositoryImpl()

    fun provideCommunicationViewModel() : CommunicationViewModel {
        return CommunicationViewModel(communicationRepository)
    }

    fun getRepository() = communicationRepository
}