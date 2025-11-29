package com.onair.mobile.communicate.presentation.ui

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.onair.mobile.communicate.data.model.dto.TaskResponse
import com.onair.mobile.databinding.ItemTaskBinding

class TaskListAdapter(
    private val onItemClick: (TaskResponse) -> Unit
) : ListAdapter<TaskResponse, TaskListAdapter.TaskListViewHolder>(TaskDiffCallback()) {

    inner class TaskListViewHolder(val binding: ItemTaskBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): TaskListViewHolder {
        return TaskListViewHolder(ItemTaskBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    }

    override fun onBindViewHolder(
        holder: TaskListViewHolder,
        position: Int
    ) {
        val task = getItem(position)
        if (task == null) return

        val binding = holder.binding

        binding.taskName.text = task.request
        binding.equipmentName.text = task.equipmentName
        binding.root.setOnClickListener {
            onItemClick(task)
        }
        binding.taskDoneCheck.setOnClickListener {

        }
    }
}
class TaskDiffCallback : DiffUtil.ItemCallback<TaskResponse>() {
    override fun areItemsTheSame(oldItem: TaskResponse, newItem: TaskResponse): Boolean {
        // 고유 ID로 같은 아이템인지 비교
        return oldItem.id == newItem.id
    }

    override fun areContentsTheSame(oldItem: TaskResponse, newItem: TaskResponse): Boolean {
        // 데이터 클래스 자체를 비교 (내용이 같은지)
        return oldItem == newItem
    }
}