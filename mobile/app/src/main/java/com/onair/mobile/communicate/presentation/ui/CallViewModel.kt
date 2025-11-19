package com.onair.mobile.communicate.presentation.ui

import com.onair.mobile.communicate.data.source.remote.SocketHolder
import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.viewModelScope
import io.livekit.android.AudioOptions
import io.livekit.android.AudioType
import io.livekit.android.LiveKit
import io.livekit.android.LiveKitOverrides
import io.livekit.android.RoomOptions
import io.livekit.android.events.RoomEvent
import io.livekit.android.events.collect
import io.livekit.android.room.track.RemoteVideoTrack
import io.livekit.android.room.track.TrackPublication
import io.livekit.android.room.track.RemoteAudioTrack
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import io.livekit.android.room.track.Track
import kotlinx.coroutines.flow.asSharedFlow


class CallViewModel(
    val url : String,
    val token: String,
    application: Application
) : AndroidViewModel(application) {
    val room = LiveKit.create(
        appContext = application,
        overrides = LiveKitOverrides(
            audioOptions = AudioOptions(
                audioOutputType = AudioType.MediaAudioType()
            )
        ),
        options = RoomOptions(
            adaptiveStream = true,
            dynacast = true,
        )
    )
    var remoteAudioTrack : RemoteAudioTrack? = null
    // Emits a string whenever a data message is received.
    private val _dataReceived = MutableSharedFlow<String>()
    val dataReceived = _dataReceived
    val arMarkers = SocketHolder.socketClient.arMarkers
    val finishEvent = SocketHolder.socketClient.callEnd
    private val _frameState = MutableSharedFlow<ByteArray?>()
    val frameState = _frameState.asSharedFlow()
    // blueprint-canvas 영상 트랙
    private val _blueprintTrack = MutableStateFlow<RemoteVideoTrack?>(null)
    val blueprintTrack: StateFlow<RemoteVideoTrack?> = _blueprintTrack.asStateFlow()

    init {
        viewModelScope.launch {
            room.events.collect { event ->
                when (event) {
                    is RoomEvent.DataReceived -> {
                        val jsonString = event.data.toString(Charsets.UTF_8)
                        Log.d("data receive", jsonString)
                        _dataReceived.emit(jsonString)
                    }
                    is RoomEvent.FailedToConnect -> {
                        Log.e("data receive", event.error.toString())
                    }

                    // blueprint-canvas 받아오기
                    is RoomEvent.TrackSubscribed -> {
                        handleBlueprintTrackSubscribed(event.track, event.publication)
                    }
                    is RoomEvent.TrackUnsubscribed -> {
                        handleBlueprintTrackUnsubscribed(event.publications)
                    }
                    else -> {
                        Log.d("room event", "$event")
                    }
                }
            }
        }
        connectToRoom()
        viewModelScope.launch {
            arMarkers.collect { markers ->
                Log.i("CallViewModel", "🎯 ViewModel에서 AR 마커 수신: ${markers.size}")
            }
        }
        collectFrames()
    }
    private fun connectToRoom() {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                room.connect(
                    url = url,
                    token = token,
                )

                room.localParticipant.setMicrophoneEnabled(false)
                room.localParticipant.setCameraEnabled(false)

                room.remoteParticipants.values.forEach { participant ->
                    participant.audioTrackPublications.forEach { t ->
                        if (t.second is RemoteAudioTrack) {
                            remoteAudioTrack = t.second as RemoteAudioTrack
                        }
                    }
                }
            } catch (e: Throwable) {
                Log.e("connectToRoom", "연결 중 오류 발생"+e.message.toString())
            }
        }
    }
    private fun collectFrames() {
        viewModelScope.launch {
            SocketHolder.socketClient.videoFrames.collect { frame ->
                _frameState.emit(frame)
                Log.d("Call view model", frame.toString())
            }
        }
    }
    override fun onCleared() {
        super.onCleared()
        room.disconnect()
        room.release()
    }

    private fun handleBlueprintTrackSubscribed(track: Track?, publication: TrackPublication) {
        if (publication.name != BLUEPRINT_TRACK_NAME || publication.source != Track.Source.SCREEN_SHARE) {
            return
        }
        val remoteVideoTrack = track as? RemoteVideoTrack ?: return
        _blueprintTrack.value = remoteVideoTrack
        Log.i("CallViewModel", "📺 blueprint-canvas track subscribed sid=${remoteVideoTrack.sid}")
    }

    private fun handleBlueprintTrackUnsubscribed(publication: TrackPublication) {
        if (publication.name != BLUEPRINT_TRACK_NAME || publication.source != Track.Source.SCREEN_SHARE) {
            return
        }
        _blueprintTrack.value = null
        Log.i("CallViewModel", "🗑 blueprint-canvas track removed")
    }

    companion object {
        private const val BLUEPRINT_TRACK_NAME = "blueprint-canvas"
    }

}