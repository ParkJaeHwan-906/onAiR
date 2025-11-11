package ssafy.com.onair.webrtc.manager;

import lombok.Getter;

import java.time.LocalDateTime;
import java.util.concurrent.ConcurrentHashMap;

@Getter
public class WebRtcManager {
    private final ConcurrentHashMap<String, LocalDateTime> waitingRoomList
            = new ConcurrentHashMap<>();
}
