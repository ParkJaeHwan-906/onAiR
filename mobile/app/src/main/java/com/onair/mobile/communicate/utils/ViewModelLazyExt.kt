package com.onair.mobile.communicate.utils

import androidx.activity.ComponentActivity
import androidx.activity.viewModels
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider

typealias CreateViewModel<VM> = () -> VM

inline fun <reified VM : ViewModel> ComponentActivity.viewModelByFactory(
    noinline create: CreateViewModel<VM>
) : Lazy<VM> {
    return viewModels {
        createViewModelFactoryFactory(create)
    }
}
inline fun <reified VM : ViewModel> Fragment.activityViewModelByFactory(
    noinline create: CreateViewModel<VM>
) : Lazy<VM> {
    return activityViewModels {
        createViewModelFactoryFactory(create)
    }
}

fun <VM> createViewModelFactoryFactory(
    create: CreateViewModel<VM>
) : ViewModelProvider.Factory {
    return object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            @Suppress("UNCHECKED_CAST")
            return create() as? T
                ?: throw IllegalArgumentException("Unknown viewmodel class!")
        }
    }
}