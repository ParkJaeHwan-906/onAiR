package com.onair.mobile.communicate.presentation.ui

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import com.google.android.material.tabs.TabLayoutMediator
import com.onair.mobile.R
import com.onair.mobile.communicate.PreferenceUtil
import com.onair.mobile.communicate.data.AuthRepository
import com.onair.mobile.communicate.data.network.ApiClient
import com.onair.mobile.communicate.data.source.remote.api.ApiService
import com.onair.mobile.communicate.presentation.viewmodel.MainViewModel
import com.onair.mobile.communicate.utils.activityViewModelByFactory
import com.onair.mobile.databinding.FragmentTaskListBinding
import kotlin.getValue

class TaskListFragment: Fragment() {
    private val mainViewModel: MainViewModel by activityViewModelByFactory {
        val apiService = ApiClient.springRetrofit.create(ApiService::class.java)
        val repository = AuthRepository(apiService, PreferenceUtil)

        MainViewModel(repository)
    }
    private lateinit var binding: FragmentTaskListBinding

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        binding = FragmentTaskListBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        binding.topAppBar.title = "작업 목록"
        binding.topAppBar.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                R.id.logout_button -> {
                    mainViewModel.logout()
                    true
                }
                else -> false
            }
        }
        val tabTitleArray = arrayOf("미완료", "완료")
        binding.viewPager.adapter = TaskPagerAdapter(requireActivity())
        TabLayoutMediator(binding.tabLayout, binding.viewPager) { tab, position ->
            tab.text = tabTitleArray[position]
        }.attach()
    }
}