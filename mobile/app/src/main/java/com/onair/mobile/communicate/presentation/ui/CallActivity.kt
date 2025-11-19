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
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
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
import androidx.compose.ui.graphics.toColorLong
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.onair.mobile.communicate.data.socket.dto.ArMarker
import com.onair.mobile.communicate.utils.viewModelByFactory
import kotlinx.coroutines.delay
import org.json.JSONObject
import kotlin.collections.emptyList
import androidx.core.graphics.toColorInt
import androidx.lifecycle.lifecycleScope
import com.onair.mobile.communicate.data.source.remote.SocketHolder
import kotlinx.coroutines.launch

data class TimedPath(
    val path: Path,
    val color: Color,
    val timestamp: Long = System.currentTimeMillis()
)
lateinit var description : String
class CallActivity : ComponentActivity() {
    private val callViewModel: CallViewModel by viewModelByFactory {
        val url = intent.getStringExtra("server_url")
            ?: throw NullPointerException("url is null!")
        val token = intent.getStringExtra("token")
            ?: throw NullPointerException("token is null")
        description = intent.getStringExtra("description")
            ?: throw java.lang.NullPointerException("description is null")
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

        val socketClient = SocketHolder.socketClient
        Log.i("CallActivity", "📡 CallActivity에서 Socket 연결 상태 확인: isActive=${socketClient.isConnected()}")
        setContent {
            MaterialTheme {
                CallScreen(callViewModel)
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
private const val REMOTE_WIDTH = 480f
private const val REMOTE_HEIGHT = 360f

@Composable
fun WhiteboardCanvas(
    viewModel: CallViewModel,
    modifier: Modifier = Modifier
){
    BoxWithConstraints(modifier) {
        val screenWidth = constraints.maxWidth.toFloat()
        val screenHeight = constraints.maxHeight.toFloat()

        val (scale, offsetX, offsetY) = remember(screenWidth, screenHeight) {
            calculateTransform(screenWidth, screenHeight)
        }
        val transform: (Float, Float) -> Offset = remember(scale, offsetX, offsetY) {
            { remoteX: Float, remoteY: Float ->
                Offset(
                    x = (remoteX * scale) + offsetX,
                    y = (remoteY * scale) + offsetY
                )
            }
        }

        var completedPaths = remember { mutableStateListOf<TimedPath>() }
        var currentPath by remember { mutableStateOf<Path?>(null) }
        var currentColor by remember { mutableStateOf(Color.White) }
        var pathTrigger by remember { mutableIntStateOf(0) }

    //    var markers by remember { mutableStateOf<List<MarkerInfo>>(emptyList()) }
        val markers by viewModel.arMarkers.collectAsState(initial = emptyList<ArMarker>())
        var pulseMarkers: List<ArMarker>? = null

        val context = LocalContext.current
        LaunchedEffect(viewModel) {
            viewModel.finishEvent.collect {
                (context as? Activity)?.finish()
            }
        }

        LaunchedEffect(Unit) {
            while (true) {
                delay(100)
                pulseMarkers = markers.map { marker ->
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
                    currentColor =  Color(colorString.toColorInt())
                    if (tool == "pen") {
                        when (eventType) {
                            "draw-start" -> {
                                val p = transform(x, y)
                                currentPath = Path().apply { moveTo(p.x, p.y) }
                                pathTrigger++
                            }
                            "draw-move" -> {
                                val p = transform(x,y)
                                currentPath?.lineTo(p.x, p.y)
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
                .fillMaxSize(),
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
                            Color(timedPath.color.toColorLong()).copy(alpha = alpha).toArgb()
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
            Log.d("CallActivity marker", markers.toString())
            markers.forEach { marker ->
                val p = transform(marker.info.x, marker.info.y)
                if (marker.type == "description") {
                    DescriptionMarker(marker = marker, p.x, p.y)
                } else {
                    ArMarker(marker = marker, p.x, p.y)
                }
            }
        }
    }
//    val points = remember { mutableStateListOf<Points>() }
    // 웹이랑 똑같게
}
private fun calculateTransform(screenWidth: Float, screenHeight: Float): Triple<Float, Float, Float> {
    val scale = screenHeight / REMOTE_HEIGHT
    val scaledWidth = REMOTE_WIDTH * scale
    val offsetX = (screenWidth - scaledWidth) /2f
    val offsetY = 0f

    return Triple(scale, offsetX, offsetY)
}
@Composable
fun ArMarker(marker: ArMarker, x: Float, y: Float) {
    val transition = rememberInfiniteTransition()

    val scale by transition.animateFloat(
        initialValue = marker.info.size,
        targetValue = marker.info.size*2.0f,
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
            color = Color(marker.color.toColorInt()),
            radius = marker.info.size,
            center = Offset(x, y)
        )

        drawCircle(
            color = Color(marker.color.toColorInt()).copy(alpha = pulseAlpha),
            radius = scale,
            center = Offset(x, y),
            style = Stroke(width = 4f)
        )
    }
}
@Composable
fun DescriptionMarker(marker: ArMarker, x: Float, y: Float) {
    // MaterialCardView -> Card
    Card(
        modifier = Modifier
            .wrapContentSize()
            // XML의 layout_constraintTop... 등은 부모 레이아웃(Column 등)에서 처리
            .padding(4.dp), // 카드 자체의 외곽 여백 (선택사항)
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant // FilledStyle과 유사한 색상
        )
    ) {
        Text(
            text = description,
            style = MaterialTheme.typography.bodyMedium, // textAppearanceBodyMedium
            modifier = Modifier
                .padding(end = 10.dp) // layout_marginEnd="10dp"
                .weight(1f, fill = false) // 텍스트가 길어질 경우 처리
        )
    }
}