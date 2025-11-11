package ssafy.com.onair.webrtc.manager;

import lombok.Getter;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.concurrent.ConcurrentHashMap;

@Getter
@Component
public class WebRtcManager {
    private final ConcurrentHashMap<String, LocalDateTime> waitingRoomList
            = new ConcurrentHashMap<>();
}
