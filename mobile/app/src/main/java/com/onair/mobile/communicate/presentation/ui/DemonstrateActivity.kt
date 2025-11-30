package com.onair.mobile.communicate.presentation.ui

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Bundle
import android.util.Log
import android.view.WindowManager
import androidx.appcompat.app.AppCompatActivity
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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.draw.clip
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
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.core.graphics.toColorInt
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.onair.mobile.assistant.data.tts.MediaPlayerController
import com.onair.mobile.communicate.data.socket.dto.ArMarker
import com.onair.mobile.communicate.presentation.viewmodel.CallViewModel
import com.onair.mobile.communicate.utils.viewModelByFactory
import com.onair.mobile.databinding.ActivityDemonstrateBinding
import io.livekit.android.compose.ui.RendererType
import io.livekit.android.compose.ui.ScaleType
import io.livekit.android.compose.ui.VideoTrackView
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject
import kotlin.getValue
import kotlin.math.roundToInt

class DemonstrateActivity : AppCompatActivity() {
    private lateinit var description : String
    private lateinit var mediaPlayerController: MediaPlayerController
    private var onAirOnDialog:  OnAirOnDialog? = null
    private val TAG = "DemonstrateActivity"
    private val callViewModel: CallViewModel by viewModelByFactory {
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
    private lateinit var binding: ActivityDemonstrateBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityDemonstrateBinding.inflate(layoutInflater)
        setContentView(binding.root)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val windowInsetsController =
            WindowCompat.getInsetsController(window, window.decorView)
        windowInsetsController.systemBarsBehavior =
            WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        windowInsetsController.hide(WindowInsetsCompat.Type.systemBars())
        description = intent.getStringExtra("description")
            ?: "RC카 고장"
        Log.d("DemonstrateActivity", "OnCreate")
        initView()
    }
    private fun initView() {
        binding.overlayCompose.apply {
            setContent {
                CallScreen(callViewModel)
            }
        }
        mediaPlayerController = MediaPlayerController(this)
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                callViewModel.frameState.collect { value ->
                    value?.let {
                        val bitmap = it.toBitmap()
//                        val cropped = bitmap?.toBottomCropped()
//                        Log.d("Demonstrate Activity", bitmap.toString())
//                        Log.d("CheckBitmap", "Size: ${bitmap?.width} x ${bitmap?.height}, ByteCount: ${bitmap?.byteCount}")
                        binding.videoView.setImageBitmap(bitmap)
//                        binding.videoView.setImageBitmap(cropped)
                    }
                }
            }
        }
    }
    private fun ByteArray.toBitmap(): Bitmap? {
        return BitmapFactory.decodeByteArray(this, 0, this.size)
    }
    @Composable
    fun CallScreen(viewModel: CallViewModel) {
        val blueprintTrack by viewModel.blueprintTrack.collectAsState()
        Log.d("Call Activity", "blue: $blueprintTrack")

        Box(
            modifier = Modifier
                .fillMaxSize()
            //            .background(Color.Black)
        ) {
            WhiteboardCanvas(
                viewModel = viewModel,
                modifier = Modifier.fillMaxSize(),
            )

            blueprintTrack?.let {
                Box(
                    modifier = Modifier
                        .align(Alignment.CenterStart)
                        .padding(16.dp)
                        .size(width = 220.dp, height = 160.dp)
                        .clip(RoundedCornerShape(16.dp))
                        .background(Color.Black.copy(alpha = 0.6f))
                ) {
                    VideoTrackView(
                        videoTrack = it,
                        modifier = Modifier.fillMaxSize(),
                        passedRoom = viewModel.room,
                        mirror = false,
                        scaleType = ScaleType.Fill,
                        rendererType = RendererType.Texture,
                    )
                }
            }
        }
    }
    private val REMOTE_WIDTH = 480f
    private val REMOTE_HEIGHT = 360f

    @Composable
    fun WhiteboardCanvas(
        viewModel: CallViewModel,
        modifier: Modifier = Modifier,
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
            var currentColor by remember { mutableStateOf(androidx.compose.ui.graphics.Color.White) }
            var pathTrigger by remember { mutableIntStateOf(0) }

            //    var markers by remember { mutableStateOf<List<MarkerInfo>>(emptyList()) }
            val markers by viewModel.arMarkers.collectAsState(initial = emptyList<ArMarker>())
            var pulseMarkers: List<ArMarker>? = null

            val context = LocalContext.current
            LaunchedEffect(viewModel) {
                viewModel.finishEvent.collect {
                    showOnModal()
                    mediaPlayerController.playLocalAudio("001_onAir_서비스를_종료합니다_다른_문제사항이_있으면.mp3") {
                        Log.d("Demo", "오디오 함수 리턴")
                        hideOnModal()
                        (context as? Activity)?.finish()
                    }
                }
            }

            LaunchedEffect(viewModel) {
                viewModel.dataReceived.collect { jsonString ->
                    Log.d("damonstrate activity", jsonString)
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
                    var currentColor: androidx.compose.ui.graphics.Color? = null
                    val shadowRadius = 15f

                    val trigger = pathTrigger
                    val now = System.currentTimeMillis()
                    val fadeDurationMillis = 1000L

                    drawIntoCanvas { canvas ->
                        completedPaths.forEach { timedPath ->
                            val age = now - timedPath.timestamp
                            val alpha = ( 1.0f - (age.toFloat() / fadeDurationMillis)).coerceAtLeast(0.0f)

                            linePaint.color = androidx.compose.ui.graphics.Color.White.copy(alpha = alpha)
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
                }
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
            targetValue = marker.info.size * 2.0f,
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
        var currentColor = "#ffffff"
        if (marker.color != null) {
            currentColor = marker.color
        }

        Canvas(modifier = Modifier.fillMaxSize()) {
            drawCircle(
                color = Color(currentColor.toColorInt()),
                radius = marker.info.size,
                center = Offset(x, y)
            )

            drawCircle(
                color = Color(currentColor.toColorInt()).copy(alpha = pulseAlpha),
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
                .offset {IntOffset(x.roundToInt(), y.roundToInt()) }
                .wrapContentSize()
                .padding(10.dp), // 카드 자체의 외곽 여백 (선택사항)
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant // FilledStyle과 유사한 색상
            ),
        ) {
            Text(
                text = description,
                style = MaterialTheme.typography.bodyMedium, // textAppearanceBodyMedium
                modifier = Modifier
                    .padding(horizontal = 10.dp, vertical = 5.dp) // layout_marginEnd="10dp"
                    .weight(1f, fill = false) // 텍스트가 길어질 경우 처리
            )
        }
    }
    private fun showOnModal() {
        try {
            // 기존 모달이 있으면 먼저 숨기기
            if (onAirOnDialog != null && onAirOnDialog?.isVisible == true) {
                onAirOnDialog?.dismissAllowingStateLoss()
                onAirOnDialog = null
            }

            // 새 모달 생성 및 표시
            onAirOnDialog = OnAirOnDialog()
            onAirOnDialog?.show(supportFragmentManager, "onAiR on")
        } catch (e: Exception) {
            Log.e(TAG, "❌ [모바일] showOnModal() 오류: ${e.message}")
            e.printStackTrace()
        }
    }

    private fun hideOnModal() {
        try {
            // 방법 1: FragmentManager에서 직접 찾아서 dismiss
            try {
                val fragment = supportFragmentManager.findFragmentByTag("onAiR on")
                if (fragment != null && fragment is OnAirOnDialog) {
                    fragment.dismissAllowingStateLoss()
                }
            } catch (e: Exception) {
                Log.e(TAG, "❌ FragmentManager에서 OnAir 모달 dismiss 오류: ${e.message}")
            }

            // 방법 2: onAirOnDialog를 통해 dismiss
            if (onAirOnDialog != null) {
                try {
                    onAirOnDialog?.dismissAllowingStateLoss()
                } catch (e: Exception) {
                    Log.e(TAG, "❌ onAirOnDialog dismiss 오류: ${e.message}")
                    try {
                        onAirOnDialog?.dismiss()
                    } catch (e2: Exception) {
                        Log.e(TAG, "❌ onAirOnDialog dismiss()도 실패: ${e2.message}")
                    }
                }
            }

            onAirOnDialog = null
        } catch (e: Exception) {
            Log.e(TAG, "❌ hideOnModal() 전체 오류: ${e.message}")
            e.printStackTrace()
        }
    }

}
