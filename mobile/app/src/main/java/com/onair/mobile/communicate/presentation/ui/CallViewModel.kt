package com.onair.mobile.communicate.presentation.ui

import android.app.Application
import android.preference.PreferenceManager
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.viewModelScope
import io.livekit.android.AudioOptions
import io.livekit.android.ConnectOptions
import io.livekit.android.LiveKit
import io.livekit.android.LiveKitOverrides
import io.livekit.android.RoomOptions
import io.livekit.android.audio.AudioSwitchHandler
import io.livekit.android.events.RoomEvent
import io.livekit.android.events.collect
import io.livekit.android.room.Room
import io.livekit.android.room.datastream.incoming.TextStreamReceiver
import io.livekit.android.room.participant.Participant
import io.livekit.android.room.track.LocalScreencastVideoTrack
import io.livekit.android.room.track.video.CameraCapturerUtils
import io.livekit.android.util.flow
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

class CallViewModel(
    val url : String,
    val token: String,
    application: Application
) : AndroidViewModel(application) {
    val room = LiveKit.create(
        appContext = application,
//        overrides = LiveKitOverrides(
//            audioOptions = AudioOptions(
//                audioProcessorOptions = null
//            )
//        )
        options = RoomOptions(
            adaptiveStream = true,
            dynacast = true,
        )
    )
    private var cameraProvider: CameraCapturerUtils.CameraProvider? = null
    val audioHandler = room.audioHandler as AudioSwitchHandler

    val participants = room::remoteParticipants.flow
        .map { remoteParticipants ->
            listOf<Participant>(room.localParticipant) +
                    remoteParticipants
                        .keys
                        .sortedBy { it.value }
                        .mapNotNull { remoteParticipants[it] }
        }

    private val _error = MutableStateFlow<Throwable?>(null)

    private val _primarySpeaker = MutableStateFlow<Participant?>(null)
    val primarySpeaker : StateFlow<Participant?> = _primarySpeaker

    val activeSpeakers = room::activeSpeakers.flow

    private var localScreencastVideoTrack : LocalScreencastVideoTrack? = null

    // Controls
    val micEnabled = room.localParticipant::isMicrophoneEnabled.flow
    val cameraEnabled = room.localParticipant::isCameraEnabled.flow
    val screenshareEnabled = room.localParticipant::isScreenShareEnabled.flow

    private val _enhancedNsEnabled = MutableStateFlow(false)
    val enhancedNsEnabled = _enhancedNsEnabled.asStateFlow()

    private val _enableAudioProcessor = MutableStateFlow(true)
    val enableAudioProcessor = _enableAudioProcessor.asStateFlow()

    // Emits a string whenever a data message is received.
    private val _dataReceived = MutableSharedFlow<String>()
    val dataReceived = _dataReceived

    // Whether other participants are allowed to subscribe to this participant's tracks.
    private val _permissionAllowed = MutableStateFlow(true)
    val permissionAllowed = _permissionAllowed.asStateFlow()

    init {
//        room.registerTextStreamHandler(
//            topic = "1k.chat",
//            handler = { receiver: TextStreamReceiver, identity: Participant.Identity ->
//                viewModelScope.launch {
//                    val message = receiver.readAll().joinToString(" ")
//                    _dataReceived.emit("$identity: $message")
//                }
//            }
//        )
        viewModelScope.launch {
            room.events.collect {
                when (it) {
                    is RoomEvent.DataReceived -> {
                        val jsonString = it.data.toString(Charsets.UTF_8)
                        _dataReceived.emit(jsonString)
                    }
                    is RoomEvent.FailedToConnect -> {
                        Log.e("data receive", it.error.toString())
                    }
                    else -> {
                        Log.d("room event", "$it")
                    }
                }
            }
        }
        connectToRoom()
    }
    private fun connectToRoom() {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                room.connect(
                    url = url,
                    token = token,
//                    options = ConnectOptions(autoSubscribe = false)
                )

                room.localParticipant.setMicrophoneEnabled(true)
                room.localParticipant.setCameraEnabled(true)
            } catch (e: Throwable) {
                Log.e("connectToRoom", "연결 중 오류 발생"+e.message.toString())
            }
        }
//        try {
//            room.connect(
//                url = url,
//                token = token,
//            )
//            _enhancedNsEnabled.postValue(room.audioProcessorIsEnabled)
//            _enableAudioProcessor.postValue(true)
//        }

    }

    override fun onCleared() {
        super.onCleared()
        room.disconnect()
        room.release()


    }


}