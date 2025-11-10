package com.onair.mobile.communicate.presentation.ui

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import com.onair.mobile.databinding.FragmentRecyclerviewBinding

class RecyclerViewFragment : Fragment() {
    companion object {
        private const val ARG_STATUS = "task_status"
        private lateinit var binding: FragmentRecyclerviewBinding

        fun newInstance(status: String): TaskListFragment {
            val args = Bundle().apply {
                putString(ARG_STATUS, status)
            }
            return TaskListFragment().apply {
                arguments = args
            }
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

        val status = arguments?.getString(ARG_STATUS)
    }
}