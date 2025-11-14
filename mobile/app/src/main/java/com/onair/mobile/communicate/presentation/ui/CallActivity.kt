package com.onair.mobile.communicate.presentation.ui

import android.app.Activity
import android.os.Bundle
import android.util.Log
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SmallFloatingActionButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import androidx.compose.ui.graphics.Paint
import androidx.compose.ui.graphics.PaintingStyle
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.onair.mobile.R
import com.onair.mobile.communicate.utils.viewModelByFactory
import kotlinx.coroutines.delay
import org.json.JSONObject

//data class Points(
//    val x: Float,
//    val y: Float,
//    val isStart: Boolean,
//    val color: Color,
//    val timestamp: Long = System.currentTimeMillis()
//)
data class TimedPath(
    val path: Path,
    val color: Color,
    val timestamp: Long = System.currentTimeMillis()
)
data class RawArMarker(
    val idx: Int,
    val info: MarkerInfo
)
data class MarkerInfo(
    val id: Long,
    val x: Float,
    val y: Float,
    val color: Color,
    val pulseScale: Float = 1f,
    val pulseOpacity: Float = 0.5f
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
//    val points = remember { mutableStateListOf<Points>() }
    // 웹이랑 똑같게

    var completedPaths = remember { mutableStateListOf<TimedPath>() }
    var currentPath by remember { mutableStateOf<Path?>(null) }
    var currentColor by remember { mutableStateOf(Color.White) }
    var pathTrigger by remember { mutableIntStateOf(0) }

    var markers by remember { mutableStateOf<List<MarkerInfo>>(emptyList()) }

    val context = LocalContext.current

    LaunchedEffect(Unit) {
        while (true) {
            delay(100)
            markers = markers.map { marker ->
                val newScale = marker.pulseScale + 0.03f
                val newOpacity = marker.pulseOpacity - 0.2f
                if (newScale > 1.6f) {
                    marker.copy(pulseScale = 1f, pulseOpacity = 0.5f)
                } else {
                    marker.copy(pulseScale = newScale, pulseOpacity = newOpacity)
                }
            }
        }
    }

    LaunchedEffect(viewModel) {
        viewModel.dataReceived.collect { jsonString ->
            try {
                val json = JSONObject(jsonString)
                val eventType = json.getString("event")
                val x = json.optDouble("x", 0.0).toFloat()
                val y = json.optDouble("y", 0.0).toFloat()
                val tool = json.optString("tool", "pen")

                val colorString = json.optString("color", "white")
                currentColor =  when (colorString) {
                    "red" -> Color.Red
                    "blue" -> Color.Blue
                    "yellow" -> Color.Yellow
                    else -> Color.White
                }
                if (tool == "pen") {
                    when (eventType) {
                        "draw-start" -> {
                            currentPath = Path().apply { moveTo(x, y) }
                            pathTrigger++
                        }
                        "draw-move" -> {
                            currentPath?.lineTo(x, y)
                            pathTrigger++
                        }
                        "draw-end" -> {
                            currentPath?.let {
                                completedPaths.add(
                                    TimedPath(path = it, color = currentColor)
                                )
                            }
                            currentPath = null
                            pathTrigger++
                        }
                    }
                }
            } catch (e: Exception){
                Log.e("json parsing", e.message.toString())
            }
        }
    }
    LaunchedEffect(Unit) {
        while (true) {
            val aSecondsAgo = System.currentTimeMillis() - 1000
    //앞에서부터 사라지기
//            points.removeAll { it.timestamp < twoSecondsAgo}
            completedPaths.removeAll { it.timestamp < aSecondsAgo }
            delay(100)

        }
    }
    val linePaint = remember {
        Paint().apply {
            style = PaintingStyle.Stroke
            strokeWidth = 5F
            strokeCap = StrokeCap.Round
            strokeJoin = StrokeJoin.Round
            isAntiAlias = true
        }
    }
    val frameworkPaint = remember {
        linePaint.asFrameworkPaint()
    }
    Box(
        modifier = Modifier
            .fillMaxSize()
            .pointerInput(Unit) {
                detectTapGestures { offset ->
                    val newMarker = MarkerInfo(
                        id = System.currentTimeMillis(),
                        x = offset.x,
                        y = offset.y,
                        color = Color.Red
                    )
                    markers = markers + newMarker
                }
            }
        ,
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = modifier) {
            val path = Path()
            var currentColor: Color? = null
            val shadowRadius = 15f

            drawRect(Color.Black)

            val trigger = pathTrigger
            val now = System.currentTimeMillis()
            val fadeDurationMillis = 1000L

            drawIntoCanvas { canvas ->
                completedPaths.forEach { timedPath ->
                    val age = now - timedPath.timestamp
                    val alpha = ( 1.0f - (age.toFloat() / fadeDurationMillis)).coerceAtLeast(0.0f)

                    linePaint.color = Color.White.copy(alpha = alpha)
                    frameworkPaint.setShadowLayer(
                        shadowRadius,
                        0f, 0f,
                        timedPath.color.copy(alpha = alpha).toArgb()
                    )
                    canvas.drawPath(timedPath.path, linePaint)
                }
                currentPath?.let {
                    linePaint.color = Color.White
                    frameworkPaint.setShadowLayer(
                        shadowRadius, 0f, 0f,
                        (currentColor ?: Color.White).toArgb()
                    )
                    canvas.drawPath(it, linePaint)
                }
            }
//            markers.forEach { marker ->
//                ArMarker(marker = marker)
////                val alpha = marker.pulseOpacity.coerceIn(0f, 1f)
////                drawCircle(
////                    color = marker.color.copy(alpha = alpha),
////                    radius = 100 * marker.pulseOpacity,
////                    center = Offset(marker.x, marker.y)
////                )
//            }
        }
        markers.forEach { marker ->
                ArMarker(marker = marker)
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
@Composable
fun ArMarker(marker: MarkerInfo) {
    val transition = rememberInfiniteTransition()

    val scale by transition.animateFloat(
        initialValue = 1.0f,
        targetValue = 1.5f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        )
    )
    val pulseAlpha by transition.animateFloat(
        initialValue = 0.8f,
        targetValue = 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        )
    )

    Canvas(modifier = Modifier.fillMaxSize()) {
        drawCircle(
            color = marker.color,
            radius = 40 * 1.0f,
            center = Offset(marker.x, marker.y)
        )

        drawCircle(
            color = marker.color.copy(alpha = pulseAlpha),
            radius = 100 * scale,
            center = Offset(marker.x, marker.y),
            style = Stroke(width = 4f)
        )
    }
}