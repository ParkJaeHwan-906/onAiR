package com.onair.mobile.communicate.presentation.ui

import android.os.Bundle
import android.util.Log
import android.view.View
import android.view.animation.AnimationUtils
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.onair.mobile.OnairApp
import com.onair.mobile.R
import com.onair.mobile.communicate.data.SSERepository
import com.onair.mobile.communicate.data.SseEvent
import com.onair.mobile.communicate.data.TaskRepository
import com.onair.mobile.communicate.data.api.ApiClient
import com.onair.mobile.communicate.data.api.ApiService
import com.onair.mobile.communicate.data.sse.SseClient
import com.onair.mobile.communicate.utils.viewModelByFactory
import com.onair.mobile.databinding.ActivityWorkingBinding
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import org.json.JSONObject

class WorkingActivity : AppCompatActivity() {
    private lateinit var binding: ActivityWorkingBinding
    private val workingViewModel: WorkingViewModel by viewModelByFactory {
        val apiService = ApiClient(this).getRetrofit().create(ApiService::class.java)
        val repository = TaskRepository(apiService)
        WorkingViewModel(repository)
    }
    private val sseViewModel = (application as OnairApp).sseViewModel


    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityWorkingBinding.inflate(layoutInflater)
        enableEdgeToEdge()
        setContentView(binding.root)
        initView()
        observeViewModel()
    }

    private fun initView() {
        val windowInsetsController =
            WindowCompat.getInsetsController(window, window.decorView)
        windowInsetsController.systemBarsBehavior =
            WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        windowInsetsController.hide(WindowInsetsCompat.Type.systemBars())

        val taskId = intent.getLongExtra("taskId", 0)
        val taskName = intent.getStringExtra("taskName")
        binding.taskName.text = taskName
        binding.endButton.setOnClickListener {
            workingViewModel.endTask(taskId, "")
        }
    }
    private fun observeViewModel() {
        lifecycleScope.launch {
//            repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    sseViewModel.eventFlow.collectLatest { event ->
                        Log.d("SSE_working", event.toString())
                        when (event) {
                            is SseEvent.CallRequest -> showCallRequestCard(event.data)
                            else -> Unit
                        }
                    }
                }
                launch {
                    workingViewModel.endStatus.collect { success ->
                        if (success) {
                            setResult(RESULT_OK)
                            finish()
                        } else {
                            Toast.makeText(
                                this@WorkingActivity,
                                "작업 완료 처리 실패",
                                Toast.LENGTH_SHORT).show()
                        }
                    }
                }


        }
    }
    private fun showCallRequestCard(data: JSONObject) {
        println(data)
        println(data.getString("name"))
        Log.d("SSE_show card", data.toString())
        binding.senderInfo.text = data.getString("name")
        binding.description.text = "통신을 요청합니다: ${data.getString("description")}"

        binding.callRequestCard.visibility = View.VISIBLE
        val anim = AnimationUtils.loadAnimation(this, R.anim.cardview_slide)
        binding.callRequestCard.startAnimation(anim)
    }
}