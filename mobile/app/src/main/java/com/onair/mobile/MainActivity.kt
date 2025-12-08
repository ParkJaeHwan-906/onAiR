package com.onair.mobile


import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.onair.mobile.communicate.PreferenceUtil
import com.onair.mobile.communicate.data.AuthRepository
import com.onair.mobile.communicate.data.network.ApiClient
import com.onair.mobile.communicate.data.source.remote.api.ApiService
import com.onair.mobile.communicate.presentation.viewmodel.CommunicationViewModel
import com.onair.mobile.communicate.presentation.ui.LoginActivity
import com.onair.mobile.communicate.presentation.viewmodel.MainViewModel
import com.onair.mobile.communicate.presentation.viewmodel.NavigationNext
import com.onair.mobile.communicate.presentation.ui.TaskListFragment
import com.onair.mobile.communicate.utils.viewModelByFactory
import com.onair.mobile.databinding.ActivityMainBinding
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private val mainViewModel: MainViewModel by viewModelByFactory {
        val apiService = ApiClient.springRetrofit.create(ApiService::class.java)
        val repository = AuthRepository(apiService, PreferenceUtil)

        MainViewModel(repository)
    }
    private val sseViewModel: CommunicationViewModel by lazy {
        (application as OnairApp).sseViewModel
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        val splashScreen = installSplashScreen()
        super.onCreate(savedInstanceState)

        splashScreen.setKeepOnScreenCondition {
            mainViewModel.isLoading.value
        }
        observeNavigation()
        }

    private fun observeNavigation() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                mainViewModel.navigationNext.collectLatest { target ->
                    when (target) {
                        NavigationNext.MAIN -> {
                            binding = ActivityMainBinding.inflate(layoutInflater)
                            setContentView(binding.root)
                            initView()
                            sseViewModel.startSSE()
                        }
                        NavigationNext.LOGIN -> {
                            sseViewModel.stopSSE()
                            startActivity(Intent(this@MainActivity, LoginActivity::class.java))
                            finish()
                        }
                        NavigationNext.LOADING -> {}
                    }
                }
            }
        }
    }
    private fun initView() {

        binding.bottomNavigationBar.setOnItemSelectedListener { item ->
            when(item.itemId) {
                R.id.task_list_item -> {
                    supportFragmentManager.beginTransaction().replace(
                        R.id.frame_layout, TaskListFragment()
                    ).commit()
                    true
                }
                R.id.ai_chat_list_item -> {
                    true
                }
                else -> false
            }
        }
        binding.bottomNavigationBar.selectedItemId = R.id.task_list_item
    }

}