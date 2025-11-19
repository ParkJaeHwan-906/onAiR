package com.onair.mobile.communicate.presentation.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Bundle
import android.os.PersistableBundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.onair.mobile.communicate.utils.viewModelByFactory
import com.onair.mobile.databinding.ActivityDemonstrateBinding
import kotlinx.coroutines.launch
import kotlin.getValue

class DemonstrateActivity : ComponentActivity() {
    private val callViewModel: CallViewModel by viewModelByFactory {
        val url = intent.getStringExtra("server_url")
            ?: throw NullPointerException("url is null!")
        val token = intent.getStringExtra("token")
            ?: throw NullPointerException("token is null")
        CallViewModel(
            url = url,
            token = token,
            application = application
        )
    }

    private lateinit var binding: ActivityDemonstrateBinding

    override fun onCreate(savedInstanceState: Bundle?, persistentState: PersistableBundle?) {
        super.onCreate(savedInstanceState, persistentState)
        binding = ActivityDemonstrateBinding.inflate(layoutInflater)
        setContentView(binding.root)
        initView()
    }
    private fun initView() {
        binding.overlayCompose.apply {
            setContent {
                WhiteboardCanvas(callViewModel, Modifier.fillMaxSize())
            }
        }
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                callViewModel.frameState.collect { value ->
                    value?.let {
                        val bitmap = it.toBitmap()
                        Log.d("Demonstrate Activity", bitmap.toString())
                        binding.videoView.setImageBitmap(bitmap)
                    }
                }
            }
        }
    }
    private fun ByteArray.toBitmap(): Bitmap? {
        return BitmapFactory.decodeByteArray(this, 0, this.size)
    }
}
