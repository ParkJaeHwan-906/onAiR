package com.onair.mobile.communicate.presentation.ui

import android.app.Activity
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaPlayer
import android.os.Bundle
import android.util.Log
import android.view.WindowManager
import androidx.activity.ComponentActivity
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
import com.onair.mobile.communicate.data.socket.dto.ArMarker
import com.onair.mobile.communicate.data.source.remote.SocketHolder
import com.onair.mobile.communicate.utils.viewModelByFactory
import com.onair.mobile.databinding.ActivityDemonstrateBinding
import io.livekit.android.compose.ui.RendererType
import io.livekit.android.compose.ui.ScaleType
import io.livekit.android.compose.ui.VideoTrackView
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import org.json.JSONObject
import kotlin.coroutines.resume
import kotlin.getValue
import kotlin.math.roundToInt

class DemonstrateActivity : ComponentActivity() {
    private lateinit var description : String
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
            ?: throw java.lang.NullPointerException("description is null")
        Log.d("DemonstrateActivity", "OnCreate")
        initView()
    }
    private fun initView() {
        binding.overlayCompose.apply {
            setContent {
                CallScreen(callViewModel)
            }
        }
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                callViewModel.frameState.collect { value ->
                    value?.let {
                        val bitmap = it.toBitmap()
                        Log.d("Demonstrate Activity", bitmap.toString())
                        Log.d("CheckBitmap", "Size: ${bitmap?.width} x ${bitmap?.height}, ByteCount: ${bitmap?.byteCount}")
                        binding.videoView.setImageBitmap(bitmap)
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
                        .align(Alignment.BottomStart)
                        .padding(16.dp)
                        .size(width = 220.dp, height = 160.dp)
                        .clip(RoundedCornerShape(16.dp))
                        .background(androidx.compose.ui.graphics.Color.Black.copy(alpha = 0.6f))
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
    private val REMOTE_WIDTH = 600f
    private val REMOTE_HEIGHT = 680f

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
                    context.playAssetAudio("001_onAir_서비스를_종료합니다_다른_문제사항이_있으면.mp3")
                    (context as? Activity)?.finish()
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
                            linePaint.color = androidx.compose.ui.graphics.Color.White
                            frameworkPaint.setShadowLayer(
                                shadowRadius, 0f, 0f,
                                (currentColor ?: androidx.compose.ui.graphics.Color.White).toArgb()
                            )
                            canvas.drawPath(it, linePaint)
                        }
                    }
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
    suspend fun Context.playAssetAudio(fileName: String) = suspendCancellableCoroutine<Unit> { continuation ->
        // MediaPlayer를 함수 내부에서 생성
        val mediaPlayer = MediaPlayer()
        Log.d("CallActivity", "MediaPlayer 재생")

        try {
            // assets 폴더에서 파일 열기
            val afd = this.assets.openFd(fileName)

            // 핵심: offset과 length를 같이 넘겨줘야 함
            mediaPlayer.setDataSource(afd.fileDescriptor, afd.startOffset, afd.length)
            afd.close() // fd는 설정 후 닫아도 됨

            mediaPlayer.setOnCompletionListener {
                it.release()
                // 재생이 끝나면 코루틴 재개 (finish()가 호출될 수 있게 함)
                if (continuation.isActive) continuation.resume(Unit)
            }

            mediaPlayer.setOnErrorListener { _, _, _ ->
                // 에러 나면 멈추지 말고 그냥 종료로 넘어가게 처리
                mediaPlayer.release()
                if (continuation.isActive) continuation.resume(Unit)
                true
            }

            mediaPlayer.prepare() // 로컬 파일이므로 동기 prepare 사용
            mediaPlayer.start()

            // 코루틴이 취소되면(화면 이탈 등) 플레이어도 해제
            continuation.invokeOnCancellation {
                try {
                    if (mediaPlayer.isPlaying) mediaPlayer.stop()
                    mediaPlayer.release()
                } catch (e: Exception) { e.printStackTrace() }
            }

            // 재생이 끝나면 메모리 해제 (중요: UI 없는 "단발성" 재생이므로 스스로 해제해야 함)
            mediaPlayer.setOnCompletionListener { mp ->
                mp.release()
            }

        } catch (e: Exception) {
            Log.e("AudioPlayer", "재생 실패: $fileName", e)
            mediaPlayer.release() // 에러 발생 시에도 해제
        }
    }
}
