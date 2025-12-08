package com.onair.mobile.communicate.presentation.ui

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.activity.result.contract.ActivityResultContracts
import androidx.fragment.app.Fragment
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.android.material.divider.MaterialDividerItemDecoration
import com.onair.mobile.communicate.data.TaskRepository
import com.onair.mobile.communicate.data.network.ApiClient
import com.onair.mobile.communicate.data.source.remote.api.ApiService
import com.onair.mobile.communicate.presentation.viewmodel.TaskListViewModel
import com.onair.mobile.communicate.utils.activityViewModelByFactory
import com.onair.mobile.databinding.FragmentRecyclerviewBinding
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

class RecyclerViewFragment : Fragment() {
    companion object {
        private const val ARG_STATUS = "task_status"
        fun newInstance(status: String): RecyclerViewFragment {
            val args = Bundle().apply {
                putString(ARG_STATUS, status)
            }
            return RecyclerViewFragment().apply {
                arguments = args
            }
        }
    }
    private lateinit var taskAdapter : TaskListAdapter
    private lateinit var binding: FragmentRecyclerviewBinding
    private val viewModel: TaskListViewModel by activityViewModelByFactory {
        val apiService = ApiClient.springRetrofit.create(ApiService::class.java)
        val repository = TaskRepository(apiService)
        TaskListViewModel(repository)
    }
    private val launcher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            viewModel.getTaskList()
        }
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        binding = FragmentRecyclerviewBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        binding.taskListRecyclerview.apply {
            taskAdapter = TaskListAdapter() { task ->
                val intent = Intent(requireContext(), DemoWorkingActivity::class.java)
                intent.putExtra("taskId", task.id)
                intent.putExtra("taskName", task.request)
                launcher.launch(intent)
            }
            adapter = taskAdapter
            layoutManager = LinearLayoutManager(requireActivity())

            val divider = MaterialDividerItemDecoration(requireActivity(), LinearLayoutManager.VERTICAL).apply {

                isLastItemDecorated = false
            }
            addItemDecoration(divider)
        }
        loadTasks()
    }

    private fun loadTasks() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                val status = arguments?.getString(ARG_STATUS)

                if (status == "미완료") {
                    viewModel.incompletedTask.collectLatest { tasks ->
                        taskAdapter.submitList(tasks)
                    }
                } else {
                    viewModel.completedTask.collectLatest { tasks ->
                        taskAdapter.submitList(tasks)
                    }
                }
            }
        }
    }
}