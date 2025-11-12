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
import com.onair.mobile.communicate.data.SSERepository
import com.onair.mobile.communicate.data.api.ApiClient
import com.onair.mobile.communicate.data.api.ApiService
import com.onair.mobile.communicate.data.sse.SseClient
import com.onair.mobile.communicate.presentation.ui.CommunicationViewModel
import com.onair.mobile.communicate.presentation.ui.LoginActivity
import com.onair.mobile.communicate.presentation.ui.MainViewModel
import com.onair.mobile.communicate.presentation.ui.NavigationNext
import com.onair.mobile.communicate.presentation.ui.TaskListFragment
import com.onair.mobile.communicate.utils.viewModelByFactory
import com.onair.mobile.databinding.ActivityMainBinding
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private val mainViewModel: MainViewModel by viewModelByFactory {
        val apiService = ApiClient(this).getRetrofit().create(ApiService::class.java)
        val repository = AuthRepository(apiService, PreferenceUtil(applicationContext))

        MainViewModel(repository)
    }
//    private val sseViewModel: CommunicationViewModel by viewModelByFactory {
//        val okHttpClient = ApiClient(this).getOkHttpClient()
//        val sseRepo = SSERepository(
//            SseClient(okHttpClient, "/task/stream")
//        )
//        CommunicationViewModel(sseRepo)
//    }
//    private val sseViewModel = (application as OnairApp).sseViewModel
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