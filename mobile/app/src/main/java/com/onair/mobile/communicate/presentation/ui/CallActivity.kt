package com.onair.mobile.communicate.presentation.ui

import android.app.Activity
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
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SmallFloatingActionButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.ReusableComposition
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.onair.mobile.R
import com.onair.mobile.communicate.utils.viewModelByFactory
import kotlinx.coroutines.delay
import org.json.JSONObject

data class Points(
    val x: Float,
    val y: Float,
    val isStart: Boolean,
    val color: Color,
    val timestamp: Long = System.currentTimeMillis()
)
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
        val windowInsetsController =
            WindowCompat.getInsetsController(window, window.decorView)
        windowInsetsController.systemBarsBehavior =
            WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        windowInsetsController.hide(WindowInsetsCompat.Type.systemBars())
        Log.d("CALL", "Call Activity 호출")
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
    val points = remember { mutableStateListOf<Points>() }
    val context = LocalContext.current

    LaunchedEffect(viewModel) {
        viewModel.dataReceived.collect { jsonString ->
            try {
                val json = JSONObject(jsonString)
                val eventType = json.getString("event")
                val x = json.optDouble("x", 0.0).toFloat()
                val y = json.optDouble("y", 0.0).toFloat()
                val tool = json.optString("tool", "pen")

                val colorString = json.optString("color", "white")
                val color =  when (colorString) {
                    "red" -> Color.Red
                    "blue" -> Color.Blue
                    "yellow" -> Color.Yellow
                    else -> Color.White
                }
// 앞에서부터 사라지기
                if (tool == "pen") {
                    when (eventType) {
                        "draw-start" -> {
                            points.add(Points(x = x, y = y, isStart = true, color = color))
                        }
                        "draw-move" -> {
                            points.add(Points(x = x, y = y, isStart = false, color = color))
                        }
                    }
                }
            } catch (e: Exception){
                Log.e("json parsing", e.message.toString())
            }
        }
    }
    //앞에서부터 사라지기
    LaunchedEffect(Unit) {
        while (true) {
            val twoSecondsAgo = System.currentTimeMillis() - 2000
            points.removeAll { it.timestamp < twoSecondsAgo}
            delay(100)
        }
    }
    Box(
        modifier = Modifier
            .fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = modifier) {
            val path = Path()
            var currentColor: Color? = null

            drawRect(Color.Black)
            //앞에서부터 사라지기 >>>>>
            points.forEach { point ->

                if (point.isStart && !path.isEmpty) {
                    drawPath(
                        path = path,
                        color = currentColor ?: Color.White
                    )
                    path.reset()
                }
                currentColor = point.color

                if (point.isStart) {
                    path.moveTo(point.x, point.y)
                } else {
                    path.lineTo(point.x, point.y)
                }
            }
            // <<<<
            if (!path.isEmpty) {
                drawPath(
                    path = path,
                    color = currentColor ?: Color.White,
                    style = Stroke(width = 5F, cap = StrokeCap.Round, join = StrokeJoin.Round)
                )
            }
        }
        SmallFloatingActionButton(
            onClick = { (context as? Activity)?.finish() },
            containerColor = MaterialTheme.colorScheme.secondaryContainer,
            contentColor = MaterialTheme.colorScheme.secondary
        ) {
            Icon(painterResource(R.drawable.ic_call_end), "통신 끊기")
        }
    }
}