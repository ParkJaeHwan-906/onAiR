package com.onair.mobile.communicate.presentation.ui

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.onair.mobile.MainActivity
import com.onair.mobile.communicate.PreferenceUtil
import com.onair.mobile.communicate.data.AuthRepository
import com.onair.mobile.communicate.data.network.ApiClient
import com.onair.mobile.communicate.data.source.remote.api.ApiService
import com.onair.mobile.communicate.presentation.viewmodel.LoginViewModel
import com.onair.mobile.databinding.ActivityLoginBinding
import kotlinx.coroutines.launch

class LoginActivity : AppCompatActivity() {
    private lateinit var binding: ActivityLoginBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLoginBinding.inflate(layoutInflater)
        enableEdgeToEdge()
        setContentView(binding.root)

        val apiService = ApiClient(this).getRetrofit().create(ApiService::class.java)
        val repository = AuthRepository(apiService, PreferenceUtil(this))
        val viewModel = LoginViewModel(repository)

        binding.loginButton.setOnClickListener {
            val email = binding.editId.text.toString()
            val password = binding.editPw.text.toString()
            viewModel.login(email, password)
        }

        lifecycleScope.launch {
            viewModel.loginState.collect { state ->
                if (state) {
                    startActivity(Intent(this@LoginActivity, MainActivity::class.java))
                    finish()
                } else {
                    Toast.makeText(this@LoginActivity, viewModel.errorMassage.value, Toast.LENGTH_SHORT)
                }
            }
        }
    }
}