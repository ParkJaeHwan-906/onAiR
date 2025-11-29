package com.onair.mobile.communicate.presentation.ui

import android.graphics.Color
import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.DialogFragment
import androidx.core.graphics.drawable.toDrawable
import androidx.core.view.isVisible
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
            .asGif()
            .load(R.drawable.start_logo)
            .into(gif)
    }
//    fun showOnModal() {
//        try {
//            // 기존 모달이 있으면 먼저 숨기기
//            if (binding.root.isVisible) {
//                binding.root?.dismissAllowingStateLoss()
//                onAirOnDialog = null
//            }
//
//            // 새 모달 생성 및 표시
//            onAirOnDialog = OnAirOnDialog()
//            onAirOnDialog?.show(supportFragmentManager, "onAiR on")
//        } catch (e: Exception) {
//            Log.e(TAG, "❌ [모바일] showOnModal() 오류: ${e.message}")
//            e.printStackTrace()
//        }
//    }
}