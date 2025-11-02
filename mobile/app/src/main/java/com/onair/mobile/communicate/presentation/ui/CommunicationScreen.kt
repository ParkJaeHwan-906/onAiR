import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import com.onair.mobile.communicate.presentation.ui.CommunicationViewModel


@Composable
fun CommunicationScreen(
//    defaultUrl: String,
//    defaultToken : String,
    defaultSecondToken: String,
    onConnect: (url: String, token: String) -> Unit = {_,_ -> },
//    onSave: (url: String, token: String) -> Unit = {_, _ -> },
//    onReset: () -> Unit = {}
) {
//    var url by remember { mutableStateOf(defaultUrl) }
//    var token by remember { mutableStateOf(defaultToken) }
    var url by remember { mutableStateOf("wss://onair-tbfd0pr1.livekit.cloud") }
    var token by remember { mutableStateOf("") }
    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
            modifier = Modifier
                .padding(16.dp)
                .verticalScroll(rememberScrollState())
        ) {
            OutlinedTextField(
                value = token,
                onValueChange = { token = it },
                label = { Text("Token") },
                modifier = Modifier.fillMaxSize()
            )
            Spacer(Modifier.height(40.dp))

            Button(
                onClick = {
                    onConnect(url, token)
                },
                modifier = Modifier.fillMaxWidth().height(50.dp)
            ) {
                Text("Connect")
            }
        }
    }
//    val lines by viewModel.lines.collectAsState()
//
//    Box(modifier = Modifier.fillMaxSize().padding(8.dp)) {
//        Canvas(modifier = Modifier.fillMaxSize()) {
//            for (line in lines) {
//                for (i in 0 until line.points.size -1) {
//                    val start = Offset((line.points[i].x).toFloat(), line.points[i].y.toFloat())
//                    val end = Offset(line.points[i + 1].x.toFloat(), line.points[i + 1].y.toFloat())
//                    drawLine(
//                        color = Color.White,
//                        start = start,
//                        end = end,
//                        alpha = 1f,
//                        strokeWidth = 2F,
//                        cap = StrokeCap.Round,
//                    )
//                }
//            }
//        }
//    }


    }