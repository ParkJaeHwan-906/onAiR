package com.onair.mobile.communicate.presentation.ui

import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.viewpager2.adapter.FragmentStateAdapter

class TaskPagerAdapter(fragmentActivity: FragmentActivity) : FragmentStateAdapter(fragmentActivity) {
    override fun createFragment(position: Int): Fragment {
        return when (position) {
            0 -> RecyclerViewFragment.newInstance("INCOMPLETE")
            1 -> RecyclerViewFragment.newInstance("COMPLETED")
            else -> throw IllegalStateException("Invalid position")
        }
    }
    override fun getItemCount(): Int = 2
}