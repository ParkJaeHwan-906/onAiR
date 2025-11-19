package com.onair.mobile.communicate.presentation.ui

import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.DialogFragment
import androidx.core.graphics.drawable.toDrawable
import com.bumptech.glide.Glide
import com.onair.mobile.R
import com.onair.mobile.databinding.DialogAiOnBinding

class AiOnDialog(val statusMessage: String) : DialogFragment(
) {

    private lateinit var binding: DialogAiOnBinding

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        dialog?.window?.setBackgroundDrawable(Color.TRANSPARENT.toDrawable())
        isCancelable = false

        binding = DialogAiOnBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val gif = binding.aiOnGif
        Glide.with(this)
            .asGif()
            .load(R.drawable.logo_gif)
            .into(gif)

        binding.aiStatusText.text = statusMessage
    }
    
    fun updateMessage(newMessage: String) {
        if (::binding.isInitialized) {
            binding.aiStatusText.text = newMessage
        }
    }
}