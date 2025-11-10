package com.onair.mobile.communicate.presentation.ui

import android.content.Context
import android.content.Intent
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.onair.mobile.communicate.data.api.dto.TaskResponse
import com.onair.mobile.databinding.ItemTaskBinding

class TaskListAdapter(
    private val items: List<TaskResponse>,
    private val context: Context
) : RecyclerView.Adapter<RecyclerView.ViewHolder>() {

    inner class TaskListViewHolder(val binding: ItemTaskBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
        return TaskListViewHolder(ItemTaskBinding.inflate(LayoutInflater.from(parent.context), parent, false))
    }

    override fun getItemCount(): Int {
        return items.size
    }

    override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
        val binding = (holder as TaskListViewHolder).binding
        val task = items[position]

        val layoutParams = binding.root.layoutParams as ViewGroup.MarginLayoutParams

        binding.taskName.text = task.request
        binding.equipmentName.text = task.equipmentName
        binding.root.setOnClickListener {
            val intent = Intent(context, WorkingActivity::class.java)
            intent.putExtra("taskId", task.id)
            context.startActivity(intent)
        }
    }
}