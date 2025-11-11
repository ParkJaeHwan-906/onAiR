package com.onair.mobile.communicate.presentation.ui

import android.os.Bundle
import android.util.Log
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.ComposeView
import com.onair.mobile.communicate.utils.viewModelByFactory
import org.json.JSONObject

class CallActivity : ComponentActivity() {
    private val viewModel: CallViewModel by viewModelByFactory {
        val url = intent.getStringExtra("server_url")
            ?: throw NullPointerException("url is null!")
        val token = intent.getStringExtra("token")
            ?: throw NullPointerException("token is null")
        CallViewModel(
            url = url,
            token = token,
            application = application
        )
    }
    private lateinit var composeView: ComposeView

    private val screenCaptureIntentLauncher =
        registerForActivityResult(
            ActivityResultContracts.StartActivityForResult(),
        ) { result ->
            val resultCode = result.resultCode
            val data = result.data
            if (resultCode != RESULT_OK || data == null) {
                return@registerForActivityResult
            }
//            viewModel.startScreenCapture(data)
        }
    @OptIn(ExperimentalMaterial3Api::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContent {
            MaterialTheme {
                CallScreen(viewModel)
            }
        }
    }
}

@Composable
fun CallScreen(viewModel: CallViewModel) {
//    val activity = (LocalContext.current as? Activity)

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
    ) {
        WhiteboardCanvas(
            viewModel = viewModel,
            modifier = Modifier.fillMaxSize(),

        )
    }
}

@Composable
fun WhiteboardCanvas(
    viewModel: CallViewModel,
    modifier: Modifier = Modifier
){
    // ✅ "지금 그리는 펜" (currentPath)을 Path()로 초기화. null일 필요 없음
    val currentPath = remember { Path() }

    // ✅ "완성된 펜"들
    val completedPaths = remember { mutableStateListOf<Path>() }

    // ✅ "다시 그려!" 신호기
    var pathTrigger by remember { mutableIntStateOf(0) }

    LaunchedEffect(viewModel) {
        viewModel.dataReceived.collect { jsonString ->
            try {
                val json = JSONObject(jsonString)
                val eventType = json.getString("event")
                val x = json.optDouble("x", 0.0).toFloat()
                val y = json.optDouble("y", 0.0).toFloat()

                when (eventType) {
//                    "draw-start" -> {
//                        val newPath = Path().apply { moveTo(x, y) }
//
//                        currentPath = newPath
//                    }
//                    "draw-move" -> {
//                        currentPath?.lineTo(x, y)
//                    }
//                    "draw-end" -> {
//                        completedPaths.add(Path())
//                        currentPath?.let { completedPaths.add(it) }
//                        currentPath = null
//                        pathTrigger++
//                    }
                    "draw-start" -> {
                        // ✅ "지금 펜"으로 (x, y) 이동
                        currentPath.moveTo(x, y)
                        pathTrigger++
                    }
                    "draw-move" -> {
                        // ✅ "지금 펜"으로 선 긋기
                        currentPath.lineTo(x, y)
                        // ✅ (핵심!) "다시 그려!" 신호 주기
                        pathTrigger++
                    }
                    "draw-end" -> {
                        val newCompletedPath = Path()
                        newCompletedPath.addPath(currentPath)
                        completedPaths.add(newCompletedPath)
                        currentPath.reset()
                        pathTrigger++
                    }
                }
            } catch (e: Exception){
                Log.e("json parsing", e.message.toString())
            }
        }
    }
    Canvas(modifier = modifier) {
        val trigger = pathTrigger
        drawRect(Color.Black)
        completedPaths.forEach { path ->
            drawPath(
                path = path,
                color = Color.White,
                style = Stroke(
                    width = 1F,
                    cap = StrokeCap.Round,
                    join = StrokeJoin.Round,
                )
            )
        }

    }

}