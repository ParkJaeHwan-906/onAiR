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
import com.onair.mobile.databinding.DialogOnairOnBinding

class OnAirOnDialog() : DialogFragment(
) {

    private lateinit var binding: DialogOnairOnBinding

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        dialog?.window?.setBackgroundDrawable(Color.TRANSPARENT.toDrawable())
        isCancelable = false

        binding = DialogOnairOnBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val gif = binding.aiOnGif
        Glide.with(this)
            .load(R.drawable.start_logo)
            .into(gif)
    }
}