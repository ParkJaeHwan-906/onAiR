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
import com.onair.mobile.assistant.domain.entity.IntentType
import com.onair.mobile.databinding.DialogAiOnBinding

class AiOnDialog(val intentType: IntentType) : DialogFragment(
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

        when (intentType) {
            IntentType.AI_SUPPORTER -> {
                binding.aiStatusText.text = "AI Support On"
            }
            IntentType.OPERATOR -> binding.aiStatusText.text = "OnAiR 서비스 시작"
            IntentType.UNKNOWN -> ""
        }
    }
}