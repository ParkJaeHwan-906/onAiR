package com.onair.mobile.communicate.presentation.ui

import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.graphics.drawable.toDrawable
import androidx.fragment.app.DialogFragment
import androidx.fragment.app.FragmentManager
import com.airbnb.lottie.LottieConfig
import com.onair.mobile.databinding.DialogLoadingBinding

class LoadingDialog : DialogFragment() {
    private lateinit var binding: DialogLoadingBinding

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        dialog?.window?.setBackgroundDrawable(Color.TRANSPARENT.toDrawable())
        isCancelable = false

        binding = DialogLoadingBinding.inflate(inflater, container, false)
        return binding.root
    }

    fun showLoading(manager: FragmentManager) {
        show(manager, "loading")
    }

    fun hideLoading() {
        dismiss()
    }

}