package com.onair.mobile.communicate.presentation.ui

import android.app.Activity
import android.os.Bundle
import android.os.PersistableBundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.onair.mobile.communicate.data.TaskRepository
import com.onair.mobile.communicate.data.api.ApiClient
import com.onair.mobile.communicate.data.api.ApiService
import com.onair.mobile.communicate.utils.viewModelByFactory
import com.onair.mobile.databinding.ActivityWorkingBinding
import kotlinx.coroutines.launch

class WorkingActivity : AppCompatActivity() {
    private lateinit var binding: ActivityWorkingBinding
    private val viewModel: WorkingViewModel by viewModelByFactory {
        val apiService = ApiClient(this).getRetrofit().create(ApiService::class.java)
        val repository = TaskRepository(apiService)

        WorkingViewModel(repository)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityWorkingBinding.inflate(layoutInflater)
        setContentView(binding.root)
        initView()
        observeViewModel()
    }
    private fun initView() {
        val taskId = intent.getLongExtra("taskId", 0)
        val taskName = intent.getStringExtra("taskName")
        binding.taskName.text = taskName
        binding.endButton.setOnClickListener {
            viewModel.endTask(taskId, "")
        }
    }
    private fun observeViewModel() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.endStatus.collect { success ->
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
}