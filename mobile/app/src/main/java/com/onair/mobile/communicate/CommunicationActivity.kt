package com.onair.mobile.communicate

import CommunicationScreen
import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.compose.ui.platform.ComposeView
import androidx.core.content.ContextCompat
import com.onair.mobile.communicate.presentation.ui.CommunicationViewModel
import com.onair.mobile.communicate.utils.DependencyProvider
import com.onair.mobile.databinding.ActivityCommunicationBinding
import io.livekit.android.room.Room

class CommunicationActivity  : ComponentActivity() {
    private val viewModel by viewModels<CommunicationViewModel>()
    private lateinit var room : Room

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
//        binding = ActivityCommunicationBinding.inflate(layoutInflater)
//        setContentView(binding.root)
        requireNeededPermissions {
            setContent {
                CommunicationScreen(
                    "",
                    onConnect = { url, token ->
                        val intent = Intent(this, CallActivity::class.java).apply {
                            putExtra("server_url", url)
                            putExtra("token", token)
                        }
                        startActivity(intent)
                    })
            }
        }

    }
    private fun initViews() {
//        val communicationViewModel = DependencyProvider.provideCommunicationViewModel()

        requireNeededPermissions()
        setContent {

        }

    }

    private fun requireNeededPermissions(onPermissionGranted: (() -> Unit)? = null) {
        val requestPermissionLauncher =
            registerForActivityResult(
                ActivityResultContracts.RequestMultiplePermissions()
            ) { grants ->
                for (grant in grants.entries) {
                    if (!grant.value) {
                        Toast.makeText(
                            this,
                            "Missing Permission: ${grant.key}",
                            Toast.LENGTH_LONG
                        )
                            .show()
                    }
                }
                if (onPermissionGranted != null && grants.all { it.value }) {
                    onPermissionGranted()
                }
            }
        val needPermissions = listOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.CAMERA)
            .filter { ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_DENIED }
            .toTypedArray()

        if (needPermissions.isNotEmpty()) {
            requestPermissionLauncher.launch(needPermissions)
        } else {
            onPermissionGranted?.invoke()
        }
    }



}