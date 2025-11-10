package com.onair.mobile


import CommunicationScreen
import android.content.Intent
import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.onair.mobile.communicate.CallActivity
import com.onair.mobile.communicate.CommunicationActivity
import com.onair.mobile.communicate.utils.DependencyProvider
import com.onair.mobile.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        enableEdgeToEdge()
        setContentView(binding.root)
//        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main)) { v, insets ->
//            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
//            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
//            insets
//        }
        // TODO: nextButton이 레이아웃에서 제거되어 주석 처리됨 (테스트 화면으로 변경)
        // binding.nextButton.setOnClickListener {
        //     val intent = Intent(this, CommunicationActivity::class.java).apply {
        //     }
        //     startActivity(intent)
        // }


    }
}